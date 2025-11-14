import json
import google.generativeai as genai
import mysql


class QueryDecomposer:
    def __init__(self, api_key: str, db1_config: dict, db2_config: dict):
        try:
            genai.configure(api_key=api_key)
            self.model_name = "gemini-2.5-flash"
            print("QueryDecomposer: Gemini client configured successfully.")
        except Exception as e:
            print(f"Error configuring Gemini client: {e}")
            raise

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

        self.system_prompt = self._build_system_prompt()
        self.generation_config = {"response_mime_type": "application/json"}
        self.model = genai.GenerativeModel(
            model_name=self.model_name,
            generation_config=self.generation_config,
            system_instruction=self.system_prompt,
        )

    def _fetch_schema_string(self, db_config: dict) -> str:
        """
        Connects to a database and builds a schema string
        by querying INFORMATION_SCHEMA.
        """
        schema_string = ""
        db_name = db_config.get("database")

        try:
            conn = mysql.connector.connect(**db_config)
            cursor = conn.cursor(dictionary=True)

            cursor.execute(
                "SELECT table_name FROM INFORMATION_SCHEMA.TABLES WHERE table_schema = %s",
                (db_name,),
            )
            tables = cursor.fetchall()

            if not tables:
                raise Exception(f"No tables found in database {db_name}")

            for table in tables:
                table_name = table["table_name"]
                schema_string += f"CREATE TABLE {table_name} (\n"

                cursor.execute(
                    """
                    SELECT column_name, column_type, is_nullable, column_key 
                    FROM INFORMATION_SCHEMA.COLUMNS 
                    WHERE table_schema = %s AND table_name = %s
                    ORDER BY ordinal_position
                """,
                    (db_name, table_name),
                )
                columns = cursor.fetchall()

                col_definitions = []
                for col in columns:
                    col_def = f"    {col['column_name']} {col['column_type']}"
                    if col["is_nullable"] == "NO":
                        col_def += " NOT NULL"
                    if col["column_key"] == "PRI":
                        col_def += " PRIMARY KEY"
                    col_definitions.append(col_def)

                cursor.execute(
                    """
                    SELECT column_name, referenced_table_name, referenced_column_name 
                    FROM INFORMATION_SCHEMA.KEY_COLUMN_USAGE 
                    WHERE table_schema = %s AND table_name = %s AND referenced_table_name IS NOT NULL
                """,
                    (db_name, table_name),
                )
                fks = cursor.fetchall()

                for fk in fks:
                    col_definitions.append(
                        f"    FOREIGN KEY ({fk['column_name']}) REFERENCES {fk['referenced_table_name']}({fk['referenced_column_name']})"
                    )

                schema_string += ",\n".join(col_definitions)
                schema_string += "\n);\n"

            cursor.close()
            conn.close()
            return schema_string

        except Exception as e:
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
            year bigint,
            yield_ton_per_hectare double,
            area_hectares double,
            production_tonnes double,
            FOREIGN KEY (district_id) REFERENCES districts(district_id),
            FOREIGN KEY (crop_id) REFERENCES crops(crop_id)
        );
        """

    def _build_system_prompt(self):
        """Constructs a detailed system prompt to guide the LLM to generate valid MySQL."""
        return f"""You are an expert SQL query generator for a federated agriculture system. 
Your task is to decompose a user's natural language query into a JSON execution plan.

--- DATA SOURCES ---
You have access to two TOTALLY SEPARATE MySQL databases. You CANNOT JOIN across them.

**DB1 (Weather & Soil)** Schema:
{self.db1_schema}

**DB2 (Crops & Yields)** Schema:
{self.db2_schema}

--- CRITICAL SQL RULES ---
1.  **MySQL Dialect:** Generate standard, valid MySQL 8.0+ queries.
2.  **No Cross-Database Joins:** A single SQL query MUST NOT reference tables from both DB1 and DB2.
3.  **Explicit Joins:** Always use explicit `JOIN` syntax (e.g., `JOIN districts ON ...`).
4.  **No Subqueries in ORDER BY:** Do not use complex subqueries in `ORDER BY` clauses.
5.  **Filtering:** If a user asks about a `state` or `district`, include that `WHERE` clause in BOTH queries if applicable.
6.  **MEDIATOR KEY MANDATE (COMPOSITE KEY):** The columns **'district' AND 'year'** MUST be in the SELECT list of EVERY SQL query (use aliases d.district, h.year, w.year). These are the critical join keys for the Python Mediator.
7.  **AGGREGATION HANDLING (YEARLY):**
    - If the user asks for "average rainfall", "total rainfall", or "average temperature" for a `year`, you MUST use `AVG()` or `SUM()` on the `weather_data` table and you MUST `GROUP BY d.district, w.year`.
    - This is essential to aggregate monthly data (DB1) to match the yearly data (DB2).
8.  **`only_full_group_by` COMPLIANCE (NEW CRITICAL RULE):**
    - To prevent Error 1055, when you use `GROUP BY`, every column in the `SELECT` list MUST be either:
        a) In the `GROUP BY` clause.
        b) An aggregate function (e.g., `SUM()`, `AVG()`, `MAX()`, `MIN()`).
    - **Example:** `SELECT d.district, h.year, SUM(h.production_tonnes)` is valid with `GROUP BY d.district, h.year`.
    - **Example:** `SELECT d.district, h.year, h.production_tonnes` is **INVALID** with `GROUP BY d.district, h.year`.

--- OUTPUT FORMAT ---
You MUST return a single JSON object with these exact keys:
- `"db1_sql"`: valid MySQL query for DB1, or "N/A" if not needed.
- `"db2_sql"`: valid MySQL query for DB2, or "N/A" if not needed.
- `"llm_prompt"`: The part of the user's query that CANNOT be answered by the databases (e.g., requests for advice, explanations, or general knowledge).

--- CRITICAL RULE FOR llm_prompt ---
- **ONLY** generate a prompt if the user explicitly asks for "advice", "recommendations", "explanations", "practices", or "why".
- For purely factual queries (what, where, when, how much, total, average, list, compare, find), the `llm_prompt` **MUST** be "N/A".

--- EXAMPLES (UPDATED) ---
User: "Rice yield in Punjab in 2022"
JSON:
{{
  "db1_sql": "N/A",
  "db2_sql": "SELECT d.district, h.year, h.yield_ton_per_hectare FROM historical_yields h JOIN districts d ON h.district_id = d.district_id JOIN crops c ON h.crop_id = c.crop_id WHERE d.state = 'Punjab' AND c.crop_name = 'Rice' AND h.year = 2022",
  "llm_prompt": "N/A"
}}

User: "Compare the soil type and average rainfall in 2023 with the Wheat production for Ambala and Karnal."
JSON:
{{
  "db1_sql": "SELECT d.district, w.year, s.soil_type, AVG(w.avg_rainfall_mm) AS avg_yearly_rainfall FROM weather_data w JOIN districts d ON w.district_id = d.district_id JOIN soil_conditions s ON d.district_id = s.district_id WHERE w.year = 2023 AND d.district IN ('Ambala', 'Karnal') GROUP BY d.district, w.year, s.soil_type",
  "db2_sql": "SELECT d.district, h.year, SUM(h.production_tonnes) AS total_wheat_production FROM historical_yields h JOIN districts d ON h.district_id = d.district_id JOIN crops c ON h.crop_id = c.crop_id WHERE h.year = 2023 AND d.district IN ('Ambala', 'Karnal') AND c.crop_name = 'Wheat' GROUP BY d.district, h.year",
  "llm_prompt": "N/A"
}}
"""

    def decompose(self, user_query: str):
        """
        Takes a user query and returns the decomposed plan as a dictionary.
        """
        response = None
        print(f"\nAnalyzing query with Gemini: '{user_query}'")
        try:
            response = self.model.generate_content([user_query])
            decomposed_plan = json.loads(response.text)
            return decomposed_plan
        except Exception as e:
            print(f"An error occurred while communicating with the Gemini API: {e}")
            try:
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

                if response_text:
                    return {
                        "error": f"An error occurred: {str(e)}. Response text: {response_text}"
                    }
                else:
                    return {
                        "error": f"An error occurred: {str(e)}. No response text captured."
                    }
