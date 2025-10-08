import streamlit as st
import json
import pandas as pd
import google.generativeai as genai
from src.decomposer import QueryDecomposer
from src.db_executor import execute_db1_query, execute_db2_query_via_api

# --- Configuration ---
DB1_CONFIG = {
    "user": "groez_user",
    "password": "groez09",
    "host": "localhost",
    "port": 3306,
    "database": "groez_db1",
}

# --- IMPORTANT ---
# Make sure this is updated with your partner's actual local network IP address.
DB2_API_URL = "http://192.168.52.99:5000/query"

# --- Streamlit Page Setup ---
st.set_page_config(page_title="GroEZ Smart Agriculture", layout="wide")
st.title("🌾 GroEZ - Smart Agriculture Query System")
st.write(
    f"_Federated query system operational as of {pd.Timestamp.now().strftime('%A, %B %d, %Y at %I:%M %p %Z')} from New Delhi, India._"
)

# --- Session State Management ---
if "decomposer" not in st.session_state:
    st.session_state.decomposer = None
if "query_result" not in st.session_state:
    st.session_state.query_result = None

# --- Data Execution Functions ---


def execute_llm_knowledge_query(llm_prompt: str):
    """
    Executes the prompt for the LLM as the third independent data source.
    """
    if not st.session_state.decomposer or not llm_prompt or llm_prompt == "N/A":
        return "N/A"

    final_prompt = (
        "You are an agricultural knowledge base. Provide a direct and factual answer to the following query. "
        f"QUERY: {llm_prompt}"
    )
    try:
        generation_model = genai.GenerativeModel("gemini-2.5-flash-preview-05-20")
        response = generation_model.generate_content(final_prompt)
        return response.text
    except Exception as e:
        return f"An error occurred while querying the LLM knowledge source: {e}"


def synthesize_final_answer(
    original_query: str,
    db1_data: pd.DataFrame,
    db2_data: pd.DataFrame,
    llm_knowledge: str,
):
    """
    Takes data from all three sources and synthesizes a final, user-friendly answer.
    Returns the final answer and the prompt used to generate it.
    """
    context = ""
    if db1_data is not None and not db1_data.empty:
        context += f"\n-- Factual Data from Weather/Soil Database (DB1) --\n{db1_data.to_string()}\n"
    if db2_data is not None and not db2_data.empty:
        context += f"\n-- Factual Data from Crop Yields Database (DB2) --\n{db2_data.to_string()}\n"
    if llm_knowledge and llm_knowledge != "N/A":
        context += f"\n-- Contextual Knowledge from Agricultural LLM Source --\n{llm_knowledge}\n"

    if not context.strip():
        context = "\n-- No data was fetched from any source for this query. --\n"

    synthesis_prompt = (
        "You are an expert agricultural analyst. Your task is to synthesize the information gathered from multiple data sources into a single, cohesive, and actionable answer for the user. "
        "Do not mention the database names or the fact that you are synthesizing data. Just provide the final answer directly as if you knew it all along.\n"
        f"DATA SOURCES PROVIDE THE FOLLOWING INFORMATION:\n{context}\n"
        f"BASED ON THE ABOVE, ANSWER THE USER'S ORIGINAL QUERY: '{original_query}'\n\n"
    )
    try:
        generation_model = genai.GenerativeModel("gemini-2.5-flash-preview-05-20")
        response = generation_model.generate_content(synthesis_prompt)
        return response.text, synthesis_prompt
    except Exception as e:
        return f"An error occurred during final answer synthesis: {e}", synthesis_prompt


# --- Sidebar for System Status ---
with st.sidebar:
    st.header("System Status")
    if not st.session_state.decomposer:
        with st.spinner("Initializing Gemini Decomposer..."):
            try:
                api_key = st.secrets["GEMINI_API_KEY"]
                st.session_state.decomposer = QueryDecomposer(api_key=api_key)
                st.success("Decomposer Initialized!")
            except Exception as e:
                st.error(
                    "Initialization failed. Check your .streamlit/secrets.toml file."
                )

# --- Main Application Area ---
st.subheader("Ask a question about agriculture in Punjab or Maharashtra")
user_query = st.text_input(
    "Enter your query:",
    placeholder="e.g., What was the total production of Sugarcane in Maharashtra in 2023?",
)
submit_button = st.button("Get Answer")

if submit_button and user_query:
    if not st.session_state.decomposer:
        st.error("System not initialized. Check sidebar for status.")
    else:
        with st.spinner(
            "Analyzing query, fetching from all sources, and synthesizing final answer..."
        ):
            decomposed_plan = st.session_state.decomposer.decompose(user_query)
            results_payload = {
                "plan": decomposed_plan,
                "db1_data": None,
                "db2_data": None,
                "llm_knowledge": "N/A",
                "final_answer": "N/A",
                "final_synthesis_prompt": "N/A",
            }

            if "error" not in decomposed_plan:
                # Execute DB1 Query
                db1_sql = decomposed_plan.get("db1_sql")
                if db1_sql and db1_sql != "N/A":
                    res, cols = execute_db1_query(DB1_CONFIG, db1_sql)
                    if res is not None:
                        results_payload["db1_data"] = pd.DataFrame(res, columns=cols)

                # Execute DB2 Query (with chaining logic)
                db2_sql = decomposed_plan.get("db2_sql")
                if db2_sql and db2_sql != "N/A":
                    placeholder = "<LIST_OF_DISTRICT_IDS_FROM_DB1>"
                    db1_results_df = results_payload.get("db1_data")
                    if placeholder in db2_sql:
                        if (
                            db1_results_df is not None
                            and not db1_results_df.empty
                            and "district_id" in db1_results_df.columns
                        ):
                            district_ids = db1_results_df["district_id"].tolist()
                            ids_string = (
                                str(tuple(district_ids))
                                if len(district_ids) > 1
                                else f"({district_ids[0]})"
                            )
                            final_db2_sql = db2_sql.replace(placeholder, ids_string)
                            res, cols = execute_db2_query_via_api(
                                DB2_API_URL, final_db2_sql
                            )
                            if res is not None:
                                results_payload["db2_data"] = pd.DataFrame(
                                    res, columns=cols
                                )
                        else:
                            results_payload["db2_data"] = pd.DataFrame()
                    else:
                        res, cols = execute_db2_query_via_api(DB2_API_URL, db2_sql)
                        if res is not None:
                            results_payload["db2_data"] = pd.DataFrame(
                                res, columns=cols
                            )

                # Execute LLM Knowledge Query
                llm_prompt_from_plan = decomposed_plan.get("llm_prompt")
                results_payload["llm_knowledge"] = execute_llm_knowledge_query(
                    llm_prompt_from_plan
                )

                # Synthesize Final Answer
                final_answer, final_prompt = synthesize_final_answer(
                    user_query,
                    results_payload["db1_data"],
                    results_payload["db2_data"],
                    results_payload["llm_knowledge"],
                )
                results_payload["final_answer"] = final_answer
                results_payload["final_synthesis_prompt"] = final_prompt

            st.session_state.query_result = results_payload

# --- Display Area for Results ---
if st.session_state.query_result:
    st.divider()
    st.subheader("Query Results")
    result = st.session_state.query_result

    st.markdown("### Final Integrated Answer")
    st.success(result["final_answer"])

    with st.expander(
        "Show Technical Details (Execution Plan & Raw Data)", expanded=False
    ):
        plan = result["plan"]
        st.write("**Analysis:**", plan.get("analysis", "N/A"))

        st.markdown("---")
        st.write("**DB1 SQL Query (Weather & Soil):**")
        st.code(plan.get("db1_sql", "N/A"), language="sql")
        if result["db1_data"] is not None:
            st.dataframe(result["db1_data"])

        st.markdown("---")
        st.write("**DB2 SQL Query (Crop Yields):**")
        st.code(plan.get("db2_sql", "N/A"), language="sql")
        if result["db2_data"] is not None:
            st.dataframe(result["db2_data"])

        st.markdown("---")
        st.write("**LLM Knowledge Query (Data Source 3):**")
        st.info(plan.get("llm_prompt", "N/A"))
        if result["llm_knowledge"] != "N/A":
            st.write("#### Knowledge from LLM Source:")
            st.write(result["llm_knowledge"])

        st.markdown("---")
        st.write("**Final Prompt Sent for Synthesis:**")
        st.info(result.get("final_synthesis_prompt", "Prompt was not generated."))
