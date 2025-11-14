import mysql.connector
from mysql.connector import Error
import google.generativeai as genai
import pandas as pd


class FederationEngine:
    def __init__(self, db1_config, db2_config, gemini_api_key):
        """Initializes the engine with DB configs, API key, and cache."""
        self.db1_config = db1_config
        self.db2_config = db2_config
        self.report_cache = {}

        try:
            genai.configure(api_key=gemini_api_key)
            self.model_name = "gemini-2.5-flash"
            self.synthesis_model = genai.GenerativeModel(self.model_name)
            print("FederationEngine: Gemini client configured successfully.")
        except Exception as e:
            print(f"Error configuring Gemini client: {e}")
            raise

    def _execute_query(self, config, query, db_label):
        """Executes a SQL query on a given database and returns a DataFrame."""
        if not query or query == "N/A":
            return None, None

        host = config.get("host", "unknown-ip")
        db = config.get("database", "unknown-db")
        print(f"\n🚀 FEDERATING: Sending SQL to {db_label} ({db}) on {host}...")
        print(f"   SQL: {query}")

        try:
            connection = mysql.connector.connect(**config)
            if connection.is_connected():
                df = pd.read_sql(query, connection)
                print(f"✅ SUCCESS: Fetched {len(df)} rows from {db_label}.")
                return df, None
        except Error as e:
            print(f"MySQL Error on {db_label}: {e}")
            return None, f"Error on {db_label}: {e}"
        finally:
            if "connection" in locals() and connection.is_connected():
                connection.close()

    def _get_llm_data(self, prompt):
        """Gets unstructured data from the LLM."""
        if not prompt or prompt == "N/A":
            return "N/A", None

        prompt = f"""You are an expert agricultural consultant. A user has asked for specific advice.
User's request: "{prompt}"

Provide a direct, factual answer to their request.
**CRITICAL:** Do NOT include any greeting, preamble, or conversational fluff like 'Hello!', 'Certainly!', or 'As an agricultural analyst...'.
Just provide the answer directly."""

        try:
            response = self.synthesis_model.generate_content(prompt)
            return response.text, None
        except Exception as e:
            print(f"LLM Error (Data): {e}")
            return None, f"Error getting LLM data: {e}"

    def _synthesize_final_report(self, user_query, joined_df, db1_df, db2_df, llm_data):
        structured_json = "N/A"
        synthesis_prompt = ""

        if joined_df is not None and not joined_df.empty:
            structured_json = joined_df.to_json(orient="records")

            synthesis_prompt = f"""You are an expert agricultural analyst. Your task is to synthesize data from multiple sources into a single, comprehensive answer for a farmer.

Original User Query: "{user_query}"

You have successfully performed a join and retrieved the following **INTEGRATED STRUCTURED DATA**:
{structured_json}

You have also retrieved the following General Advice (from a separate LLM query):
{llm_data}

---
Task:
Integrate all of this information into a single, fluid, and easy-to-understand response.
- Start by directly answering the user's query.
- Use the **INTEGRATED STRUCTURED DATA** to support your factual claims.
- Weave in the general advice where it's relevant.
- Do not just list the data; synthesize it. If the structured data is 'N/A' or empty, state that fact politely.
"""

        else:
            print(
                "ℹ️ Manual join failed or was not applicable. Synthesizing using SEPARATE data."
            )
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

            synthesis_prompt = f"""You are an expert agricultural analyst. Your task is to synthesize data from multiple sources into a single, comprehensive answer for a farmer.

Original User Query: "{user_query}"

The system could not perform a direct join. You have retrieved the following **SEPARATE UN-JOINED DATA** from two different databases:

Data from DB1 (Weather/Soil):
{db1_json}

Data from DB2 (Crops/Yields):
{db2_json}

You have also retrieved the following General Advice (from a separate LLM query):
{llm_data}

---
Task:
IntegrATE all of this information into a single, fluid, and easy-to-understand response.
- Look at the user's query and use the data from the **SEPARATE** sources to answer it.
- You may need to manually compare or correlate the data in your reasoning.
- Weave in the general advice where it's relevant.
- Do not just list the data; synthesize it.
"""

        try:
            response = self.synthesis_model.generate_content(synthesis_prompt)
            return response.text
        except Exception as e:
            print(f"LLM Error (Synthesis): {e}")
            return f"Error during final synthesis: {e}"

    def run(self, decomposed_plan: dict, user_query: str):
        db1_sql = decomposed_plan.get("db1_sql")
        db2_sql = decomposed_plan.get("db2_sql")
        llm_prompt = decomposed_plan.get("llm_prompt")

        errors = []
        joined_structured_df = pd.DataFrame()

        db1_results_df, db1_err = self._execute_query(
            self.db1_config, db1_sql, "DB1 (Local)"
        )
        if db1_err:
            errors.append(db1_err)

        db2_results_df, db2_err = self._execute_query(
            self.db2_config, db2_sql, "DB2 (Remote)"
        )
        if db2_err:
            errors.append(db2_err)

        try:
            if (
                db1_results_df is not None
                and not db1_results_df.empty
                and db2_results_df is not None
                and not db2_results_df.empty
            ):
                required_keys = ["district", "year"]

                if all(key in db1_results_df.columns for key in required_keys) and all(
                    key in db2_results_df.columns for key in required_keys
                ):
                    joined_structured_df = pd.merge(
                        db1_results_df,
                        db2_results_df,
                        on=required_keys,
                        how="inner",
                        suffixes=("_db1", "_db2"),
                    )
                    print(
                        f"✅ Manual Pandas Composite Join successful. Result size: {len(joined_structured_df)} rows."
                    )

                else:
                    errors.append(
                        "Manual Join Failed: Composite key ('district' and 'year') not found in one or both query results. Check LLM compliance."
                    )

            # Only DB1 returned data
            elif db1_results_df is not None and not db1_results_df.empty:
                joined_structured_df = db1_results_df  # Pass it along
                print("Only DB1 returned data. Using as structured result.")

            # Only DB2 returned data
            elif db2_results_df is not None and not db2_results_df.empty:
                joined_structured_df = db2_results_df  # Pass it along
                print("Only DB2 returned data. Using as structured result.")

        except Exception as e:
            errors.append(f"Manual Join Failed: {e}")

        llm_data, llm_err = self._get_llm_data(llm_prompt)
        if llm_err:
            errors.append(llm_err)

        final_answer = self._synthesize_final_report(
            user_query,
            joined_structured_df,
            db1_results_df,
            db2_results_df,
            llm_data,
        )

        report = {
            "title": f"GroEZ Analysis for: '{user_query}'",
            "db_results_db1": db1_results_df,
            "db_results_db2": db2_results_df,
            "db_joined_results": joined_structured_df,
            "llm_data": llm_data,
            "final_integrated_answer": final_answer,
            "errors": errors,
        }

        return report
