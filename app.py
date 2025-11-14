import streamlit as st
from src.decomposer import QueryDecomposer
from src.federation_engine import FederationEngine
from config import DB1_CONFIG, DB2_CONFIG, GEMINI_API_KEY

st.set_page_config(
    page_title="GroEZ: Smart Agri Query",
    page_icon="🌾",
    layout="wide",
    initial_sidebar_state="expanded",
)


@st.cache_resource(ttl=3600)
def init_engine():
    """Initializes the federation engine and decomposer."""
    try:
        engine = FederationEngine(DB1_CONFIG, DB2_CONFIG, GEMINI_API_KEY)
        decomposer = QueryDecomposer(
            api_key=GEMINI_API_KEY, db1_config=DB1_CONFIG, db2_config=DB2_CONFIG
        )
        return engine, decomposer
    except Exception as e:
        st.error(
            f"Failed to initialize. Please check API key and DB connections. Error: {e}"
        )
        return None, None


engine, decomposer = init_engine()


if engine and decomposer:
    # --- Sidebar ---
    st.sidebar.title("About GroEZ 🌾")
    st.sidebar.info(
        """
        It uses a federated architecture to integrate:
        - In One Database, we have Weather & Soil Data
        - In another, we have Crop and Historical Yields data
        - We take general knowledge data from an LLM
        """
    )

    # --- Main Page ---
    st.title("GroEZ: Smart Agriculture Query System")

    if "user_query" not in st.session_state:
        st.session_state.user_query = ""

    query_text = "Compare the average Wheat yield in 2022 for districts with 'Alluvial' soil versus 'Red' soil."
    user_query = st.text_area(
        "Enter your questions:",
        value=st.session_state.user_query,
        height=100,
        placeholder=query_text,
    )

    if st.button("Submit Query"):
        if user_query:
            st.session_state.user_query = user_query

            with st.spinner("Analyzing and decomposing query..."):
                plan = decomposer.decompose(user_query)

            with st.spinner("Federating queries, executing..."):
                report = engine.run(plan, user_query)

            st.divider()
            st.subheader("Analysis Complete")

            with st.expander("Show Execution Plan (Decomposed Queries)"):
                st.json(plan)

            with st.expander("Show Raw Data from Databases"):
                st.markdown("#### **Data from DB1 (Weather & Soil)**")
                if (
                    report.get("db_results_db1") is not None
                    and not report["db_results_db1"].empty
                ):
                    st.dataframe(report["db_results_db1"], width="stretch")
                else:
                    st.info("No data returned from DB1 for this query.")

                st.markdown("#### **Data from DB2 (Crops & Yields)**")
                if (
                    report.get("db_results_db2") is not None
                    and not report["db_results_db2"].empty
                ):
                    st.dataframe(report["db_results_db2"], width="stretch")
                else:
                    st.info("No data returned from DB2 for this query.")

            with st.expander("Show JOINED data (merged after federation)"):
                if (
                    report.get("db_joined_results") is not None
                    and not report["db_joined_results"].empty
                ):
                    st.markdown("#### **Merged DATA**")
                    st.dataframe(report["db_joined_results"], width="stretch")
                else:
                    st.info("No common structured data was found to join.")

            with st.expander("Show Raw Advice (from LLM)"):
                if report["llm_data"] and report["llm_data"] != "N/A":
                    st.info(f"{report['llm_data']}")
                else:
                    st.info("No general knowledge recommendations were requested.")

            # Show Final Integrated Summary
            st.markdown("### Integrated Summary")
            st.success(report["final_integrated_answer"])
            st.markdown("---")

            if report["errors"]:
                with st.expander("Show Errors Encountered", expanded=True):
                    for err in report["errors"]:
                        st.error(err)

        else:
            st.warning("Please enter a query.")


else:
    st.error(
        "Application could not start. Please check terminal for initialization errors."
    )
