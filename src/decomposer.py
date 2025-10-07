import json
import google.generativeai as genai


class QueryDecomposer:
    """
    Analyzes a natural language query using the Google Gemini API and decomposes it
    into sub-queries for structured databases and a prompt for a general knowledge LLM.
    """

    def __init__(self, api_key: str):
        """
        Initializes the decomposer by configuring the Gemini client with an API key.

        Args:
            api_key: The API key for the Google AI Studio (Gemini).
        """
        try:
            genai.configure(api_key=api_key)
            print("Google Gemini client configured successfully.")
        except Exception as e:
            print(f"Error configuring Gemini client: {e}")
            raise

        self.db1_schema = self._get_db1_schema()
        self.db2_schema = self._get_db2_schema()
        self.system_prompt = self._build_system_prompt()
        self.generation_config = {"response_mime_type": "application/json"}

        self.model = genai.GenerativeModel(
            model_name="gemini-2.5-flash",
            generation_config=self.generation_config,
            system_instruction=self.system_prompt,
        )

    def _get_db1_schema(self):
        """Returns the schema for DB1 as a string."""
        return """
        -- DB1 (groez_db1) contains data on weather and soil conditions.
        CREATE TABLE districts (
            district_id INT PRIMARY KEY,
            district VARCHAR(255),
            state VARCHAR(255)
        );
        CREATE TABLE soil_conditions (
            district_id INT,
            soil_type VARCHAR(255),
            ph_level FLOAT,
            nitrogen_ppm INT,
            phosphorus_ppm INT,
            potassium_ppm INT,
            FOREIGN KEY (district_id) REFERENCES districts(district_id)
        );
        CREATE TABLE weather_data (
            district_id INT,
            year INT,
            month INT,
            avg_temp_celsius FLOAT,
            avg_rainfall_mm FLOAT,
            FOREIGN KEY (district_id) REFERENCES districts(district_id)
        );
        """

    def _get_db2_schema(self):
        """Returns the schema for DB2 as a string."""
        return """
        -- DB2 (groez_db2) contains data on crop types and historical yields.
        CREATE TABLE districts (
            district_id INT PRIMARY KEY,
            district VARCHAR(255),
            state VARCHAR(255)
        );
        CREATE TABLE crops (
            crop_id INT PRIMARY KEY,
            crop_name VARCHAR(255)
        );
        CREATE TABLE historical_yields (
            district_id INT,
            crop_id INT,
            year INT,
            yield_ton_per_hectare FLOAT,
            area_hectares INT,
            production_tonnes FLOAT,
            FOREIGN KEY (district_id) REFERENCES districts(district_id),
            FOREIGN KEY (crop_id) REFERENCES crops(crop_id)
        );
        """

    def _build_system_prompt(self):
        """Constructs the detailed system prompt for the LLM."""
        return f"""
        You are an expert query decomposition system for a smart agriculture application, operating on Tuesday, October 7, 2025, from New Delhi, India.
        Your task is to analyze a user's natural language query and break it down into sub-queries for two separate MySQL databases and a prompt for a general knowledge LLM.

        You have access to the following data sources:

        1.  **DB1 (groez_db1 - Weather & Soil)**: Contains information about regions, soil conditions, and weather.
            Schema:
            {self.db1_schema}

        2.  **DB2 (groez_db2 - Crops & Yields)**: Contains information about crops and their historical yields.
            Schema:
            {self.db2_schema}

        3.  **General LLM**: Used for questions requiring agricultural advice, recommendations, or explanations (e.g., "how to", "why", "recommend", "tips", "explain").

        **Instructions:**
        1.  Analyze the user's query to understand their intent and identify key entities (crops, locations, years, soil types etc.).
        2.  Generate the appropriate MySQL SQL query/queries for the correct database based on the entities found. Use lowercase table names.
        3.  If the query asks for advice or explanation, formulate a clear, self-contained prompt for the General LLM.
        4.  Your output MUST be a single, valid JSON object that adheres to the schema provided. Do not add any text or explanations.
        5.  The JSON object must have these exact keys: "analysis", "db1_sql", "db2_sql", "llm_prompt".
        6.  For any key that is not needed for a given query, use the string "N/A" as its value.
        """

    def decompose(self, user_query: str):
        """
        Takes a user query and returns the decomposed plan as a dictionary.
        """
        print(f"\\nAnalyzing query with Gemini: '{user_query}'")
        try:
            response = self.model.generate_content([user_query])
            decomposed_plan = json.loads(response.text)
            return decomposed_plan
        except Exception as e:
            print(f"An error occurred while communicating with the Gemini API: {e}")
            return {"error": f"An error occurred: {str(e)}"}
