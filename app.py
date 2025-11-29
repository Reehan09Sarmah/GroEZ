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
    st.sidebar.title("🌾 GroEZ")
    st.sidebar.caption("Smart Agriculture Query System")

    st.sidebar.divider()

    st.sidebar.markdown("### **Unlock Your Farm's Potential**")

    st.sidebar.info(
        """
        **Ask us anything about agriculture!**
        
        📜 **Historical Data:** Dive into agronomical archives.
        
        🚀 **Yield Advice:** Proven tips to boost production.
        
        🌍 **Land Analysis:** Know about soil inside out.
        
        🔮 **Predictions:** Simulate the future with AI.
        """
    )

    st.sidebar.success("### **📍 You are in the right place!**")

    st.title("GroEZ: Smart Agriculture Query System")

    tab1, tab2 = st.tabs(["Ask your Questions", "🔮 Predictions"])

    with tab1:
        if "user_query" not in st.session_state:
            st.session_state.user_query = ""

        query_text = "Compare the average Rice yield in 2022 for districts with 'Alluvial' soil versus 'Red' soil."
        user_query = st.text_area(
            "Enter your questions:",
            value=st.session_state.user_query,
            height=100,
            placeholder=query_text,
            key="nl_query_input",
        )

        if st.button("Submit", key="btn_fetch"):
            if user_query:
                st.session_state.user_query = user_query

                with st.spinner("Got your query..."):
                    plan = decomposer.decompose(user_query)

                if "error" in plan:
                    st.error(f"Could not understand query: {plan['error']}")
                else:
                    with st.spinner("Fetching data..."):
                        report = engine.run(plan, user_query, decomposer=decomposer)

                    st.divider()
                    st.subheader("Analysis Complete")

                    with st.expander("Show Decomposed Queries"):
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

                    with st.expander("Show Raw Advice (from LLM)"):
                        if report["llm_data"] and report["llm_data"] != "N/A":
                            st.info(f"{report['llm_data']}")
                        else:
                            st.info(
                                "No general knowledge recommendations were requested."
                            )

                    st.markdown("### **Summary**")

                    if (
                        report.get("db_joined_results") is not None
                        and not report["db_joined_results"].empty
                    ):
                        st.dataframe(report["db_joined_results"], width="stretch")

                    else:
                        st.info("Couldn't merge data!")

                    st.success(report["final_integrated_answer"])
                    st.markdown("---")

                    if report["errors"]:
                        with st.expander("Show Errors Encountered", expanded=True):
                            for err in report["errors"]:
                                st.error(err)

            else:
                st.warning("Please enter a query.")

    # TAB 2
    with tab2:
        st.header("🔮 GET YOUR PREDICTIONS!!!")
        st.info(
            "Simulate any hypothetical scenarios based on historical data patterns grounded in our database."
        )

        col1, col2 = st.columns(2)
        with col1:
            sim_district = st.text_input("Target District", "Ambala")
            sim_crop = st.text_input("Target Crop", "Rice")
        with col2:
            sim_condition = st.text_area(
                "Hypothetical Condition",
                "Rainfall decreases by 20%",
                height=100,
            )

        if st.button("Run Simulation", key="btn_sim"):
            with st.spinner(f"Checking scenario about {sim_crop} in {sim_district}..."):
                prediction = engine.simulate_scenario(
                    sim_district, sim_crop, sim_condition
                )

                st.divider()
                st.markdown("### 📊 Report")
                st.markdown(prediction)

else:
    st.error(
        "Application could not start. Please check terminal for initialization errors."
    )
