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
    st.sidebar.title("About GroEZ 🌾")
    st.sidebar.info(
        """
        It uses a federated architecture to integrate:
        - In One Database, we have Weather & Soil Data
        - In another, we have Crop and Historical Yields data
        - We take general knowledge data from an LLM
        """
    )

    st.title("GroEZ: Smart Agriculture Query System")

    # --- IIA FEATURE: TABS FOR MODES ---
    tab1, tab2 = st.tabs(["🔍 Natural Language Query", "🔮 'What-If' Simulator"])

    # -------------------------------------------------------------------------
    # TAB 1: STANDARD QUERY (Moved your existing logic here)
    # -------------------------------------------------------------------------
    with tab1:
        st.subheader("Federated Data Analysis")

        if "user_query" not in st.session_state:
            st.session_state.user_query = ""

        query_text = "Compare the average Rice yield in 2022 for districts with 'Alluvial' soil versus 'Red' soil."
        user_query = st.text_area(
            "Enter your questions:",
            value=st.session_state.user_query,
            height=100,
            placeholder=query_text,
            key="nl_query_input",  # Unique key for this widget
        )

        if st.button("Fetch Analysis", key="btn_fetch"):
            if user_query:
                st.session_state.user_query = user_query

                with st.spinner("Decomposing intent & Federating queries..."):
                    plan = decomposer.decompose(user_query)

                # Check for decomposition errors before running engine
                if "error" in plan:
                    st.error(f"Could not understand query: {plan['error']}")
                else:
                    with st.spinner("Fetching data & Synthesizing report..."):
                        report = engine.run(plan, user_query)

                    st.divider()
                    st.subheader("Analysis Complete")

                    # 1. Execution Plan
                    with st.expander("Show Execution Plan (Decomposed Queries)"):
                        st.json(plan)

                    # 2. Raw DB Results
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

                    # 3. LLM Advice
                    with st.expander("Show Raw Advice (from LLM)"):
                        if report["llm_data"] and report["llm_data"] != "N/A":
                            st.info(f"{report['llm_data']}")
                        else:
                            st.info(
                                "No general knowledge recommendations were requested."
                            )

                    # 4. Integrated Summary & Merged Data
                    st.markdown("### Integrated Summary")

                    if (
                        report.get("db_joined_results") is not None
                        and not report["db_joined_results"].empty
                    ):
                        with st.expander("View Merged Data Table", expanded=False):
                            st.dataframe(report["db_joined_results"], width="stretch")
                    else:
                        st.info("No common structured data was found to join.")

                    st.success(report["final_integrated_answer"])
                    st.markdown("---")

                    if report["errors"]:
                        with st.expander("Show Errors Encountered", expanded=True):
                            for err in report["errors"]:
                                st.error(err)

            else:
                st.warning("Please enter a query.")

    # -------------------------------------------------------------------------
    # TAB 2: PRESCRIPTIVE SIMULATION (New IIA Feature)
    # -------------------------------------------------------------------------
    with tab2:
        st.header("🔮 Prescriptive Analytics")
        st.info(
            "Simulate future scenarios based on historical data patterns grounded in your DB2 data."
        )

        col1, col2 = st.columns(2)
        with col1:
            sim_district = st.text_input("Target District", "Belgaum")
            sim_crop = st.text_input("Target Crop", "Rice")
        with col2:
            sim_condition = st.text_area(
                "Hypothetical Condition",
                "Rainfall decreases by 20% due to El Nino",
                height=100,
            )

        if st.button("Run Simulation", key="btn_sim"):
            with st.spinner(
                f"Running Prescriptive Models for {sim_crop} in {sim_district}..."
            ):
                # Call the new simulation method in engine
                prediction = engine.simulate_scenario(
                    sim_district, sim_crop, sim_condition
                )

                st.divider()
                st.markdown("### 📊 Simulation Report")
                st.markdown(prediction)

else:
    st.error(
        "Application could not start. Please check terminal for initialization errors."
    )
