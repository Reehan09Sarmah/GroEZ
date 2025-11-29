import mysql.connector
from mysql.connector import Error
import google.generativeai as genai
import pandas as pd


class FederationEngine:
    def __init__(self, db1_config, db2_config, gemini_api_key):
        self.db1_config = db1_config
        self.db2_config = db2_config
        self.report_cache = {}

        try:
            genai.configure(api_key=gemini_api_key)
            self.model_name = "gemini-2.5-flash"
            self.model = genai.GenerativeModel(self.model_name)
            self.synthesis_model = self.model
            print("FederationEngine: Gemini client configured successfully.")
        except Exception as e:
            print(f"Error configuring Gemini client: {e}")
            raise

    def _execute_query(self, config, query, db_label, attempt=1):
        if not query or query == "N/A":
            return None, None

        host = config.get("host", "unknown")
        print(f"Query to be federated: {query}")
        print(f"\n🏎️💨 FEDERATING: SQL to {db_label} ({host})... Attempt {attempt}")

        try:
            conn = mysql.connector.connect(**config)
            df = pd.read_sql(query, conn)
            conn.close()
            print(f"✅ SUCCESS: Fetched {len(df)} rows.")
            return df, None
        except Error as e:
            print(f"❌ Error: {e}")
            return None, str(e)

    def _execute_with_retry(self, config, query, db_label, user_query, decomposer):
        """
        Wrapper around _execute_query that implements the Reflexion (Self-Correction) loop.
        """
        df, error = self._execute_query(config, query, db_label, attempt=1)

        if error and decomposer:
            print(f"⚠️ Encountered Error in {db_label}: {error}")
            print("🔄 Initiating Self-Correction Loop (Reflexion)...")
            fixed_sql = decomposer.fix_query(user_query, query, error, db_label)

            if fixed_sql:
                print(f"🚀 Retrying {db_label} with Fixed SQL: {fixed_sql}")
                df_retry, error_retry = self._execute_query(
                    config, fixed_sql, db_label, attempt=2
                )
                if not error_retry:
                    print(f"✅ Self-Correction Successful for {db_label}!")
                    return df_retry, None
                else:
                    return None, f"Retry failed: {error_retry}"
            else:
                return None, "Self-correction failed to generate new SQL."

        return df, error

    def simulate_scenario(self, district, crop, condition):
        print(f"🔮 Running Simulation: {district}, {crop} -> {condition}")
        # 1. Fetch Yield History (DB2)
        sql_yields = f"""
            SELECT h.year, h.yield_ton_per_hectare, h.production_tonnes
            FROM historical_yields h
            JOIN districts d ON h.district_id = d.district_id
            JOIN crops c ON h.crop_id = c.crop_id
            WHERE d.district = '{district}' AND c.crop_name = '{crop}'
            ORDER BY h.year DESC LIMIT 5
        """
        yields_df, _ = self._execute_query(self.db2_config, sql_yields, "DB2 (Yields)")
        yields_json = (
            yields_df.to_json(orient="records")
            if yields_df is not None and not yields_df.empty
            else "No Data"
        )

        # 2. Fetch Weather History (DB1)
        sql_weather = f"""
            SELECT w.year, SUM(w.avg_rainfall_mm) as total_annual_rainfall, AVG(w.avg_temp_celsius) as avg_temp
            FROM weather_data w
            JOIN districts d ON w.district_id = d.district_id
            WHERE d.district = '{district}'
            GROUP BY w.year
            ORDER BY w.year DESC LIMIT 5
        """
        weather_df, _ = self._execute_query(
            self.db1_config, sql_weather, "DB1 (Weather)"
        )
        weather_json = (
            weather_df.to_json(orient="records")
            if weather_df is not None and not weather_df.empty
            else "No Data"
        )

        sim_prompt = f"""
        You are an Agricultural AI Simulator.
        CONTEXT: District: {district}, Crop: {crop}
        --- GROUND TRUTH DATA ---
        1. Historical Yields (DB2): {yields_json}
        2. Historical Weather (DB1): {weather_json}
        --- SIMULATION ---
        SCENARIO: "What happens if {condition}?"
        TASK: Predict impact on Yield/Production based on correlation with past data.
        """
        try:
            return self.model.generate_content(sim_prompt).text
        except Exception as e:
            return f"Simulation Failed: {e}"

    def _get_llm_data(self, prompt, db_context=""):
        """
        Fetches research/context from LLM.
        NOW ACCEPTS 'db_context' to solve the 'Population of THIS district' problem.
        """
        if not prompt or prompt == "N/A":
            return "N/A", None

        context_block = ""
        if db_context:
            context_block = f"\n\n--- CONTEXT FOUND IN DATABASES ---\n{db_context}\n----------------------------------\n"

        final_prompt = f"""You are an Expert Agricultural and General Knowledge Engine.

User Request: "{prompt}"
{context_block}
**INSTRUCTION:**
1. If the User Request refers to "this district", "these crops", or "the location", USE the information in the 'CONTEXT FOUND IN DATABASES' section above to resolve it.
2. If the user asks for Population, Demographics, or Prices, use your internal knowledge to answer for the specific entities found in the context.
3. Provide an output suitable for summarization.
"""

        try:
            response = self.model.generate_content(final_prompt)
            return response.text, None
        except Exception as e:
            print(f"LLM Error (Data): {e}")
            return None, f"Error getting LLM data: {e}"

    def _extract_context_string(self, df, label):
        """Helper to extract meaningful entities (District, State, Crop) from a DataFrame."""
        if df is None or df.empty:
            return ""

        context_parts = []
        # Case insensitive column lookup
        cols = [c.lower() for c in df.columns]

        # Check for District
        if "district" in cols:
            districts = df.iloc[:, cols.index("district")].unique()
            context_parts.append(f"Districts: {', '.join(map(str, districts))}")

        # Check for State
        if "state" in cols:
            states = df.iloc[:, cols.index("state")].unique()
            context_parts.append(f"States: {', '.join(map(str, states))}")

        # Check for Crop
        if "crop_name" in cols:
            crops = df.iloc[:, cols.index("crop_name")].unique()
            context_parts.append(f"Crops: {', '.join(map(str, crops))}")

        if context_parts:
            return f"[{label}] -> " + " | ".join(context_parts)
        return ""

    def _synthesize_final_report(self, user_query, joined_df, db1_df, db2_df, llm_data):
        structured_json = "N/A"
        if joined_df is not None and not joined_df.empty:
            structured_json = joined_df.to_json(orient="records")
        else:
            db1_json = (
                db1_df.to_json(orient="records")
                if db1_df is not None and not db1_df.empty
                else "N/A"
            )
            db2_json = (
                db2_df.to_json(orient="records")
                if db2_df is not None and not db2_df.empty
                else "N/A"
            )
            structured_json = f"DB1: {db1_json}\nDB2: {db2_json}"

        synthesis_prompt = f"""You are an Expert Synthesis Engine.
Original User Query: "{user_query}"

Integrated Structured Data (From Database):
{structured_json}

Unstructured Research Output (Contextualized):
{llm_data}

---
CRITICAL INSTRUCTION:
1. **Merge** the Structured Data (Numbers) with the Research Output (Facts/Context).
2. If the Research Output contains the population/demographics requested, include it prominently.
3. Produce a cohesive final answer.
"""
        try:
            response = self.synthesis_model.generate_content(synthesis_prompt)
            return response.text
        except Exception as e:
            return f"Error during final synthesis: {e}"

    def run(self, decomposed_plan: dict, user_query: str, decomposer=None):
        db1_sql = decomposed_plan.get("db1_sql")
        db2_sql = decomposed_plan.get("db2_sql")
        llm_prompt = decomposed_plan.get("llm_prompt")

        errors = []

        # 1. Execute DB Queries
        db1_res, db1_err = self._execute_with_retry(
            self.db1_config, db1_sql, "DB1 (Local)", user_query, decomposer
        )
        if db1_err:
            errors.append(db1_err)

        db2_res, db2_err = self._execute_with_retry(
            self.db2_config, db2_sql, "DB2 (Remote)", user_query, decomposer
        )
        if db2_err:
            errors.append(db2_err)

        # 2. Join
        joined_df = pd.DataFrame()
        try:
            if (
                db1_res is not None
                and not db1_res.empty
                and db2_res is not None
                and not db2_res.empty
            ):
                # Standardize cols
                db1_res.columns = [c.lower() for c in db1_res.columns]
                db2_res.columns = [c.lower() for c in db2_res.columns]

                common_cols = list(set(db1_res.columns) & set(db2_res.columns))
                if common_cols:
                    joined_df = pd.merge(
                        db1_res,
                        db2_res,
                        on=common_cols,
                        how="inner",
                        suffixes=("_db1", "_db2"),
                    )
                else:
                    errors.append("Join Failed: No common columns.")
            elif db1_res is not None and not db1_res.empty:
                joined_df = db1_res
            elif db2_res is not None and not db2_res.empty:
                joined_df = db2_res
        except Exception as e:
            errors.append(f"Join Processing Failed: {e}")

        # 3. Context Construction
        db_context_str = ""
        if not joined_df.empty:
            db_context_str += self._extract_context_string(joined_df, "Joined Results")
        else:
            if db1_res is not None:
                db_context_str += self._extract_context_string(db1_res, "DB1") + "\n"
            if db2_res is not None:
                db_context_str += self._extract_context_string(db2_res, "DB2") + "\n"

        # 4. Get LLM Advice
        llm_data, llm_err = self._get_llm_data(llm_prompt, db_context=db_context_str)
        if llm_err:
            errors.append(llm_err)

        final_answer = self._synthesize_final_report(
            user_query, joined_df, db1_res, db2_res, llm_data
        )

        return {
            "title": f"GroEZ Analysis for: '{user_query}'",
            "db_results_db1": db1_res,
            "db_results_db2": db2_res,
            "db_joined_results": joined_df,
            "llm_data": llm_data,
            "final_integrated_answer": final_answer,
            "errors": errors,
        }
