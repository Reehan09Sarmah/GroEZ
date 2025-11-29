import json
import google.generativeai as genai
import mysql.connector
from mysql.connector import Error


class QueryDecomposer:
    def __init__(self, api_key: str, db1_config: dict, db2_config: dict):
        # 1. Configure Gemini
        try:
            genai.configure(api_key=api_key)
            self.model_name = "gemini-2.5-flash"
            print("QueryDecomposer: Gemini client configured successfully.")
        except Exception as e:
            print(f"Error configuring Gemini client: {e}")
            raise

        # 2. Dynamic Schema Fetching
        print("QueryDecomposer: Dynamically fetching database schemas...")
        try:
            self.db1_schema = self._get_db1_schema(db1_config)
            self.db2_schema = self._get_db2_schema(db2_config)
            print("✅ QueryDecomposer: Schemas fetched successfully.")
        except Exception as e:
            print(f"CRITICAL ERROR: Could not fetch schemas from database: {e}")
            print("Falling back to hardcoded schemas. System may be unstable.")
            self.db1_schema = self._get_db1_schema_fallback()
            self.db2_schema = self._get_db2_schema_fallback()

        # Dictionary for LLM.
        self.ontology = """
--- DOMAIN ONTOLOGY (SEMANTIC MAP) ---
1. SEASONS (Mapping Months to Seasons):
   - "Kharif" (Monsoon): Months 6, 7, 8, 9, 10
   - "Rabi" (Winter): Months 11, 12, 1, 2, 3
   - "Zaid" (Summer): Months 4, 5

2. CROP CATEGORIES (Exact DB String Matches):
   - "Cereals": 'Rice', 'Wheat', 'Maize', 'Bajra', 'Ragi', 'Jowar', 'Barley', 'Small millets', 'Other Cereals'
   
   - "Pulses": 'Gram', 'Arhar/Tur', 'Urad', 'Moong(Green Gram)', 'Masoor', 'Horse-gram', 'Peas & beans (Pulses)', 'Moth', 'Khesari', 'Cowpea(Lobia)', 'Other Kharif pulses', 'Other Rabi pulses', 'Other Summer Pulses'
   
   - "Oilseeds": 'Groundnut', 'Rapeseed &Mustard', 'Soybean', 'Soyabean', 'Sunflower', 'Safflower', 'Castor seed', 'Linseed', 'Niger seed', 'Sesamum', 'other oilseeds', 'Oilseeds total'
   
   - "Cash Crops" (Commercial): 'Sugarcane', 'Cotton', 'Cotton(lint)', 'Jute', 'Mesta', 'Tobacco', 'Guar seed', 'Sannhamp'
   
   - "Spices & Condiments": 'Dry chillies', 'Black pepper', 'Cardamom', 'Coriander', 'Ginger', 'Dry Ginger', 'Turmeric', 'Garlic', 'Onion'
   
   - "Plantation/Fruits/Tubers": 'Arecanut', 'Banana', 'Cashewnut', 'Coconut', 'Potato', 'Sweet potato', 'Tapioca'

3. SOIL DEFINITIONS:
   - "Acidic": ph_level < 6.0
   - "Neutral": ph_level BETWEEN 6.0 AND 7.5
   - "Alkaline": ph_level > 7.5
   - "Nitrogen Deficient": nitrogen_ppm < 280
"""

        # Initialize the LLM API
        self.system_prompt = self._build_system_prompt()
        self.generation_config = {"response_mime_type": "application/json"}
        self.model = genai.GenerativeModel(
            model_name=self.model_name,
            generation_config=self.generation_config,
            system_instruction=self.system_prompt,
        )

    # Get schema of our DBs dynamically
    def _fetch_schema_string(self, db_config: dict) -> str:
        schema_string = ""
        db_name = db_config.get("database")

        try:
            conn = mysql.connector.connect(**db_config)
            cursor = conn.cursor(dictionary=True)

            # Fetch tables
            cursor.execute(
                "SELECT table_name FROM INFORMATION_SCHEMA.TABLES WHERE table_schema = %s",
                (db_name,),
            )
            tables = cursor.fetchall()

            if not tables:
                raise Exception(f"No tables found in database {db_name}")

            for table in tables:
                table_name = table["TABLE_NAME"]
                schema_string += f"CREATE TABLE `{table_name}` (\n"

                cursor.execute(
                    """
                    SELECT column_name, column_type, is_nullable, column_key, extra
                    FROM INFORMATION_SCHEMA.COLUMNS
                    WHERE table_schema = %s AND table_name = %s
                    ORDER BY ordinal_position
                    """,
                    (db_name, table_name),
                )
                columns = cursor.fetchall()

                col_definitions = []
                for col in columns:
                    col_def = f"    `{col['COLUMN_NAME']}` {col['COLUMN_TYPE']}"
                    if col["IS_NULLABLE"] == "NO":
                        col_def += " NOT NULL"
                    if col["EXTRA"]:
                        col_def += f" {col['EXTRA']}"
                    if col["COLUMN_KEY"] == "PRI":
                        col_def += " PRIMARY KEY"
                    col_definitions.append(col_def)

                cursor.execute(
                    """
                    SELECT column_name, referenced_table_name, referenced_column_name 
                    FROM INFORMATION_SCHEMA.KEY_COLUMN_USAGE 
                    WHERE table_schema = %s AND table_name = %s 
                    AND referenced_table_name IS NOT NULL
                    """,
                    (db_name, table_name),
                )
                fks = cursor.fetchall()

                for fk in fks:
                    col_definitions.append(
                        f"    FOREIGN KEY (`{fk['COLUMN_NAME']}`) "
                        f"REFERENCES `{fk['REFERENCED_TABLE_NAME']}`(`{fk['REFERENCED_COLUMN_NAME']}`)"
                    )

                schema_string += ",\n".join(col_definitions)
                schema_string += "\n);\n\n"

            cursor.close()
            conn.close()
            return schema_string

        except Error as e:
            print(f"Error connecting to DB {db_name} to fetch schema: {e}")
            raise e

    def _get_db1_schema(self, db1_config: dict):
        return self._fetch_schema_string(db1_config)

    def _get_db2_schema(self, db2_config: dict):
        return self._fetch_schema_string(db2_config)

    def _get_db1_schema_fallback(self):
        """Returns the hardcoded schema for DB1 if dynamic fetch fails."""
        return """
        -- DB1 (groez_db1) contains data on weather and soil conditions.
        CREATE TABLE districts (
            district_id bigint PRIMARY KEY,
            district text,
            state text
        );
        CREATE TABLE soil_conditions (
            district_id bigint,
            soil_type text,
            ph_level double,
            nitrogen_ppm bigint,
            phosphorus_ppm bigint,
            potassium_ppm bigint,
            FOREIGN KEY (district_id) REFERENCES districts(district_id)
        );
        CREATE TABLE weather_data (
            district_id bigint,
            year bigint,
            month bigint,
            avg_temp_celsius double,
            avg_rainfall_mm double,
            FOREIGN KEY (district_id) REFERENCES districts(district_id)
        );
        """

    def _get_db2_schema_fallback(self):
        """Returns the hardcoded schema for DB2 if dynamic fetch fails."""
        return """
        -- DB2 (groez_db2) contains data on crop types and historical yields.
        CREATE TABLE districts (
            district_id bigint PRIMARY KEY,
            district text,
            state text
        );
        CREATE TABLE crops (
            crop_id bigint PRIMARY KEY,
            crop_name text
        );
        CREATE TABLE historical_yields (
            district_id bigint,
            crop_id bigint,
            year VARCHAR(10),
            yield_ton_per_hectare double,
            area_hectares double,
            production_tonnes double,
            FOREIGN KEY (district_id) REFERENCES districts(district_id),
            FOREIGN KEY (crop_id) REFERENCES crops(crop_id)
        );
        """

    # Prompt to decompose text-to-SQL
    def _build_system_prompt(self):
        return f"""You are an expert SQL query generator for a federated agriculture system. 
Your task is to decompose a user's natural language query into a JSON execution plan.

--- DATA SOURCES ---
You have access to two TOTALLY SEPARATE MySQL databases. You CANNOT JOIN across them.

**DB1 (Weather & Soil)** Schema:
{self.db1_schema}

**DB2 (Crops & Yields)** Schema:
{self.db2_schema}

-- DICTIONARY FOR YOU --
{self.ontology}

--- SQL RULES ---
1. **Valid MySQL:** Use standard MySQL 8.0 syntax.
2. **Ontology:** Apply the mappings (e.g. Kharif -> Month 6-10).
3. **No Cross-DB Joins:** Queries must be independent.
4. **DISTRICT ALIGNMENT:** - You MUST select `district` (or `d.district`) in both queries if available.
   - This is the PRIMARY KEY for the Python Mediator to join data.
5. **YEARLY DATA:**
   - IF the table has a `year` column, select it.
   - IF the table DOES NOT have a `year` column (like `soil_conditions`), DO NOT fake it. Just select the district and the relevant columns. The Mediator will handle the broadcasting.
   
6. **SELECT DESCRIPTIVE COLUMNS (CRITICAL):**
   - **Never select ONLY the district.**
   - Eg: If the user filters by "Acidic soil", you MUST select `ph_level` and `soil_type` so the user can see the values.
   - Always include the columns that justify WHY a record was returned.
   
--- HYBRID DECOMPOSITION STRATEGY (CRITICAL) ---
The user query may contain a mix of "Structured Database Questions" and "Unstructured Agricultural Questions".
**You must split them.** Here are certain examples:

**Scenario A: Pure Database Query (In Schema)**
- Query: "Rice yield in Belgaum 2022"
- Action: Generate SQL for DB2. Set `llm_prompt` = "N/A".

**Scenario B: Pure Out-of-Scope Query (Agricultural but Not in Schema)**
- Query: "What is the current market price (MSP) of Cotton?" (Price is NOT in DB)
- Action: Set SQL = "N/A". Set `llm_prompt` = "What is the current market price (MSP) of Cotton?"
- Query: "My leaves have yellow spots, what disease is this?" (Disease symptoms NOT in DB)
- Action: Set SQL = "N/A". Set `llm_prompt` = "My leaves have yellow spots, what disease is this?"

**Scenario C: Hybrid (DB2 + LLM)**
- Query: "Show me Wheat yield in Punjab and tell me the best time to sell it for maximum profit."
- Action:
  - `db1_sql`: "N/A"
  - `db2_sql`: "SELECT d.district, c.crop_name, h.year, h.yield_ton_per_hectare FROM historical_yields h JOIN districts d ON h.district_id = d.district_id JOIN crops c ON h.crop_id = c.crop_id WHERE d.state='Punjab' AND c.crop_name='Wheat'"
  - `llm_prompt`: "tell me the best time to sell Wheat for maximum profit."

**Scenario D: Hybrid (DB1 + LLM)**
- Query: "Compare soil pH in Gujarat vs Punjab and list the government subsidies available for acidic soil."
- Action:
  - `db1_sql`: "SELECT d.district, d.state, s.ph_level, s.soil_type FROM soil_conditions s JOIN districts d ON s.district_id = d.district_id WHERE d.state IN ('Gujarat', 'Punjab')"
  - `db2_sql`: "N/A"
  - `llm_prompt`: "list the government subsidies available for acidic soil."

**Scenario E: Full Hybrid (DB1 + DB2 + LLM)**
- Query: "Show rainfall in Belgaum (DB1) and Rice yield in 2022 (DB2) and explain if this rainfall is sufficient for Rice according to ICAR standards."
- Action:
  - `db1_sql`: "SELECT d.district, w.year, w.avg_rainfall_mm FROM weather_data w JOIN districts d ON w.district_id = d.district_id WHERE d.district='Belgaum'"
  - `db2_sql`: "SELECT d.district, c.crop_name, h.year, h.yield_ton_per_hectare FROM historical_yields h JOIN districts d ON h.district_id = d.district_id JOIN crops c ON h.crop_id = c.crop_id WHERE d.district='Belgaum' AND c.crop_name='Rice' AND h.year=2022"
  - `llm_prompt`: "explain if this rainfall amount is sufficient for Rice according to ICAR standards."
    
- **NEVER** hallucinate tables or columns. If the data isn't there, send the task to `llm_prompt`.


--- CRITICAL RULE FOR llm_prompt ---
- **ONLY** generate a prompt if the user explicitly asks for "advice", "recommendations", "explanations", "practices", or "why" or "how", etc..
- For purely factual queries (what, where, when, how much, total, average, list, compare, find), the `llm_prompt` **MUST** be "N/A".

--- CRITICAL RULE FOR UNKNOWN DATA ---
- If the user asks for something completely unrelated to the schemas or you know this kind of data won't be retrived from our databases, do this:
    1. Set `"db1_sql"` to "N/A".
    2. Set `"db2_sql"` to "N/A".
    3. Copy the **ENTIRE** user query into `"llm_prompt"`.

--- OUTPUT FORMAT ---
You MUST return a single JSON object with these exact keys:
- `"db1_sql"`: valid MySQL query for DB1, or "N/A" if not needed.
- `"db2_sql"`: valid MySQL query for DB2, or "N/A" if not needed.
- `"llm_prompt"`: The part of the user's query that CANNOT be answered by the databases (e.g., requests for advice, explanations, or general knowledge).
"""

    # decomposes user query and gets the execution plan
    def decompose(self, user_query: str):
        response = None
        print(f"\nAnalyzing query with Gemini (with Ontology): '{user_query}'")
        try:
            response = self.model.generate_content([user_query])
            decomposed_plan = json.loads(response.text)
            return decomposed_plan
        except Exception as e:
            print(f"An error occurred while communicating with the Gemini API: {e}")
            try:
                # Retry:
                if not response:
                    response = self.model.generate_content([user_query])

                response_text = response.text

                try:
                    decomposed_plan = json.loads(response_text)
                    return decomposed_plan
                except json.JSONDecodeError as inner_e:
                    print(
                        f"CRITICAL: Failed to parse LLM response: {inner_e}. Response text: {response_text}"
                    )
                    return {
                        "error": f"CRITICAL: Failed to parse LLM response: {inner_e}. Response text: {response_text}"
                    }
            except Exception as e:
                print(f"An error occurred while communicating with the Gemini API: {e}")

                if "response_text" in locals() and response_text:
                    return {
                        "error": f"An error occurred: {str(e)}. Response text: {response_text}"
                    }
                else:
                    return {
                        "error": f"An error occurred: {str(e)}. No response text captured."
                    }

    # If somehow, it generates Wrong SQL Queries, it tries to fix it by re-calling the LLM along with the error
    def fix_query(
        self, original_query: str, bad_sql: str, error_msg: str, db_type: str
    ):
        print(f"\n🔧 SELF-CORRECTION: Attempting to fix SQL for {db_type}...")

        target_schema = self.db1_schema if "DB1" in db_type else self.db2_schema

        fix_prompt = f"""
        You act as a SQL Debugger.

        **CONTEXT:**
        User Query: "{original_query}"
        Target Database Schema: 
        {target_schema}

        **THE BUG:**
        You generated this SQL:
        {bad_sql}

        It failed with this MySQL Error:
        "{error_msg}"

        **TASK:**
        1. Analyze the error (e.g., column doesn't exist, syntax error, wrong table).
        2. Correct the SQL to be valid for the provided schema.
        3. Return ONLY the corrected SQL string in a JSON format.

        **OUTPUT FORMAT:**
        {{ "fixed_sql": "SELECT ... " }}
        """

        try:
            response = self.model.generate_content(fix_prompt)
            data = json.loads(response.text)
            fixed_sql = data.get("fixed_sql")
            print(f"✅ Fixed SQL: {fixed_sql}")
            return fixed_sql
        except Exception as e:
            print(f"❌ Could not fix query: {e}")
            return None
