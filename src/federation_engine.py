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
            self.model = genai.GenerativeModel(self.model_name)
            self.synthesis_model = self.model
            print("FederationEngine: Gemini client configured successfully.")
        except Exception as e:
            print(f"Error configuring Gemini client: {e}")
            raise

    def _execute_query(self, config, query, db_label, attempt=1):
        """Executes SQL with automatic retry (Self-Correction)."""
        if not query or query == "N/A":
            return None, None

        host = config.get("host", "unknown")
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

    def simulate_scenario(self, district, crop, condition):
        """Performs a 'What-If' analysis fetching Ground Truth from BOTH DBs."""
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
        # We aggregate monthly data to yearly to match the yield granularity
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

        # 3. Build Grounded Prompt
        sim_prompt = f"""
        You are an Agricultural AI Simulator.
        
        CONTEXT: District: {district}, Crop: {crop}
        
        --- GROUND TRUTH DATA ---
        1. Historical Yields (DB2):
        {yields_json}
        
        2. Historical Weather (DB1):
        {weather_json}
        
        --- SIMULATION ---
        SCENARIO: "What happens if {condition}?"
        
        TASK: 
        1. Analyze the correlation between past weather (DB1) and past yields (DB2).
        2. Apply the scenario condition to this baseline.
        3. Predict impact on Yield and Production with quantitative estimates.
        """

        try:
            return self.model.generate_content(sim_prompt).text
        except Exception as e:
            return f"Simulation Failed: {e}"

    def _get_llm_data(self, prompt):
        """Gets unstructured data with flexible sourcing and referencing."""
        if not prompt or prompt == "N/A":
            return "N/A", None

        # UPDATED PROMPT: More flexible, research-oriented, and sourced.
        prompt = f"""You are an Expert Agricultural Knowledge and Research Engine.

User Request: "{prompt}"

Produce an output that is suitable for downstream summarization with other structured datasets. 
The response must be factual, structured, and maximally useful for machine-processing.

Your objectives:
1. **Interpretation & Scope**
   - Identify what the user is fundamentally asking (advice, explanation, diagnosis, comparison, definition, procedure, evaluation, or data lookup).
   - Respond according to the request type without adding conversational phrasing.

2. **Core Content**
   - Provide accurate, domain-relevant knowledge.
   - When applicable, include quantitative ranges, scientific names, agronomic thresholds, environmental factors, or standard benchmarks used in agricultural R&D.
   - For non-agricultural queries, summarize the core technical or conceptual content precisely.

3. **Optional Direct Advice (Only if Requested)**
   - If the user explicitly seeks recommendations, include clear steps or guidelines.
   - Keep advice evidence-based.

4. **Evidence, References, and Standards**
   - Attribute information to known authorities when possible (e.g., [Source: ICAR], [Source: FAO], [Source: State Agriculture Dept.], [Source: Peer-Reviewed Literature]).
   - If specific sourcing is unknown, label it as [Source: General Agronomic Consensus].

5. **External Resources**
   - Suggest authoritative portals, government sites, data repositories, or document types the user may consult (e.g., mKisan, Vikaspedia, FAOSTAT, ICAR publications).

6. **Structure**
   - Use headings, bullet points, and clearly separated sections.
   - No conversational fillers, no greetings, no emotional tone.

Output must be self-contained and directly usable as unstructured research text for further summarization with factual structured data
"""

        try:
            response = self.model.generate_content(prompt)
            return response.text, None
        except Exception as e:
            print(f"LLM Error (Data): {e}")
            return None, f"Error getting LLM data: {e}"

    def _synthesize_final_report(self, user_query, joined_df, db1_df, db2_df, llm_data):
        structured_json = "N/A"
        synthesis_prompt = ""

        if joined_df is not None and not joined_df.empty:
            structured_json = joined_df.to_json(orient="records")

            synthesis_prompt = f"""You are an Expert Agricultural Synthesis Engine.

Original User Query: "{user_query}"

Integrated Structured Data (STRUCTURED DATA):
{structured_json}

Unstructured Research Output from Previous LLM Step(UNSTRUCTURED DATA):
{llm_data}

---

Task:
Produce a single, coherent synthesis that combines all available information.
The output must be analytical, concise, and directly address the user's query without any conversational language or preambles.

Mandatory Requirements:

1. **Query-First Structure**
   - Begin by resolving the user's query as precisely as possible.
   - If the question requests recommendations, provide them.
   - If the question requests explanation, comparison, diagnosis, or contextual knowledge, focus on that.
   - Avoid greetings, acknowledgments, or meta-comments.

2. **Use of Structured Data**
   - Integrate relevant facts from the STRUCTURED DATA into the explanation.
   - Do not merely restate the JSON.
   - If the structured data is "N/A" or contains no relevant entries, state this briefly and continue the synthesis without halting.

3. **Use of Unstructured Data**
   - Draw supporting context, agronomic ranges, thresholds, scientific names, and any referenced authorities from the UNSTRUCTURED DATA (the llm research output)
   - Merge these seamlessly with the structured facts.

4. **Fusion, Not Enumeration**
   - Present the final result as a unified narrative or analysis.
   - No bullet dumping of JSON values.
   - Highlight links between datasets when meaningful (e.g., "The structured dataset indicates X, which aligns with Y from the unstructured analysis").

5. **Neutral, Technical Tone**
   - No greetings, no conversational phrases, no role self-identification.
   - Use clear subheadings only if they improve clarity.
   - Avoid statements about what the system “can” or “will” do.

6. **Missing or Conflicting Information**
   - If data sources disagree, provide a short reconciliation or state the uncertainty.
   - If necessary information is absent, state the gap briefly and provide the best-possible interpretation based on available evidence.

Output must be a single, cohesive, self-contained synthesis that integrates all available evidence. can be used downstream in summarization or decision-support models. It should be easy to understand and can be applied right away.

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

            synthesis_prompt = f"""You are an Expert Agricultural Synthesis Engine.

Original User Query: "{user_query}"

The system could not perform a direct join. You now have the following SEPARATE DATA SOURCES:

DB1: Weather/Soil Information
{db1_json}

DB2: Crop/Variety/Yield Information
{db2_json}

Unstructured Research Output (General Context/Guidelines)
{llm_data}

---

Task:
Produce a single, coherent synthesis that addresses the user’s query by integrating the un-joined data sources and the unstructured research output.

Requirements:

1. Query Resolution
   - Begin by directly addressing the user’s query.
   - Identify whether the query requires explanation, comparison, diagnosis, suitability analysis, or recommendations.
   - Respond in a factual, neutral, and technical tone without conversational language.

2. Cross-Source Integration
   - Compare and correlate DB1 and DB2 manually where relevant (e.g., match soil type to crop suitability, climate to expected performance, rainfall to risk factors).
   - If correlations are weak or incomplete, state the limitations briefly and continue the synthesis.

3. Use of Unstructured Research Output
   - Integrate evidence-based context, thresholds, ranges, agronomic standards, or scientific names extracted from the unstructured text.
   - Use it only where it strengthens or clarifies the final synthesis.

4. No Enumeration or Dumping
   - Do not list raw JSON or reproduce data verbatim.
   - Transform the content into a unified analysis that links conditions, constraints, and implications.

5. Data Gaps and Uncertainty
   - If information is missing, incomplete, or contradictory across sources, note this succinctly and provide the best possible interpretation without speculation.

6. Tone and Structure
   - No greetings, no conversational filler, no role identification.
   - Clear, concise, structured explanation suitable for downstream summarization.
   - Subheadings allowed only if they improve clarity.

Provide one cohesive, internally consistent synthesis that integrates all available evidence.

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

        # 1. Execute DB Queries
        db1_res, db1_err = self._execute_query(self.db1_config, db1_sql, "DB1 (Local)")
        if db1_err:
            errors.append(db1_err)

        db2_res, db2_err = self._execute_query(self.db2_config, db2_sql, "DB2 (Remote)")
        if db2_err:
            errors.append(db2_err)

        # We join on ALL columns that share the same name.
        joined_df = pd.DataFrame()
        try:
            if (
                db1_res is not None
                and not db1_res.empty
                and db2_res is not None
                and not db2_res.empty
            ):
                # Normalize columns to lowercase to ensure matching works
                db1_res.columns = [c.lower() for c in db1_res.columns]
                db2_res.columns = [c.lower() for c in db2_res.columns]

                # Find the Natural Keys (Intersection of columns)
                common_cols = list(set(db1_res.columns) & set(db2_res.columns))

                if common_cols:
                    print(f"🔗 Strategy: Natural Join on columns: {common_cols}")
                    # By passing the list of common columns to 'on', we strictly perform a Natural Join.
                    joined_df = pd.merge(
                        db1_res,
                        db2_res,
                        on=common_cols,
                        how="inner",
                        suffixes=("_db1", "_db2"),
                    )
                else:
                    errors.append(
                        "Join Failed: No common columns found for Natural Join. (Cross Product prevented)"
                    )

            elif db1_res is not None and not db1_res.empty:
                joined_df = db1_res
            elif db2_res is not None and not db2_res.empty:
                joined_df = db2_res

        except Exception as e:
            errors.append(f"Join Processing Failed: {e}")

        # 3. Get LLM Advice & Synthesize
        llm_data, llm_err = self._get_llm_data(llm_prompt)
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
