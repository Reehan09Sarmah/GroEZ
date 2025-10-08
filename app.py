import streamlit as st
import json  
import pandas as pd
from src.decomposer import QueryDecomposer
from src.db_executor import execute_db1_query, execute_db2_query_via_api

# --- Configuration ---
# All your existing configurations remain the same.
DB1_CONFIG = {
    "user": "groez_user",
    "password": "groez09",
    "host": "localhost",
    "port": 3306,
    "database": "groez_db1"
}

# --- IMPORTANT ---
# Make sure this is updated with your partner's actual local network IP address.
DB2_API_URL = "http://192.168.52.99:5000/query" 

# --- Streamlit Page Setup ---
st.set_page_config(page_title="GroEZ Smart Agriculture", layout="wide")
st.title("🌾 GroEZ - Smart Agriculture Query System")
st.write(f"_Federated query system operational as of {pd.Timestamp.now().strftime('%A, %B %d, %Y at %I:%M %p %Z')} from New Delhi, India._")

# --- Session State Management ---
# This helps store variables like the API key and results as you interact with the app.
if 'api_key' not in st.session_state:
    st.session_state.api_key = ''
if 'decomposer' not in st.session_state:
    st.session_state.decomposer = None
if 'query_result' not in st.session_state:
    st.session_state.query_result = None

# --- Sidebar for API Key and Configuration ---
with st.sidebar:
    st.header("Configuration")
    api_key_input = st.text_input("Enter your Google AI Studio API key", type="password", value=st.session_state.api_key)
    
    # Initialize the decomposer once the API key is entered
    if api_key_input and not st.session_state.decomposer:
        st.session_state.api_key = api_key_input
        with st.spinner("Initializing Gemini Decomposer..."):
            try:
                st.session_state.decomposer = QueryDecomposer(api_key=st.session_state.api_key)
                st.success("Decomposer initialized!")
            except Exception as e:
                st.error(f"Initialization failed. Check API key. Error: {e}")
                st.session_state.decomposer = None

# --- Main Application Area ---
st.subheader("Ask a question about agriculture in Punjab or Maharashtra")
user_query = st.text_input("Enter your query:", placeholder="e.g., What was the total production of Sugarcane in Maharashtra in 2023?")
submit_button = st.button("Get Answer")

if submit_button and user_query:
    # Validate that the decomposer is ready
    if not st.session_state.decomposer:
        st.error("Please enter a valid Gemini API key in the sidebar to initialize the system.")
    else:
        with st.spinner("Analyzing your query and fetching data across the federation..."):
            # 1. Decompose the query
            decomposed_plan = st.session_state.decomposer.decompose(user_query)
            
            # Prepare a dictionary to hold all results
            results_payload = {"plan": decomposed_plan, "db1_data": None, "db2_data": None}

            if "error" not in decomposed_plan:
                # 2. Execute DB1 Query (if needed)
                db1_sql = decomposed_plan.get("db1_sql")
                if db1_sql and db1_sql != "N/A":
                    results, columns = execute_db1_query(DB1_CONFIG, db1_sql)
                    if results is not None:
                        results_payload["db1_data"] = pd.DataFrame(results, columns=columns)

                # 3. Execute DB2 Query (if needed)
                db2_sql = decomposed_plan.get("db2_sql")
                if db2_sql and db2_sql != "N/A":
                    # Critical: Partner's API must be running!
                    results, columns = execute_db2_query_via_api(DB2_API_URL, db2_sql)
                    if results is not None:
                        results_payload["db2_data"] = pd.DataFrame(results, columns=columns)
            
            # Store the final payload in the session state to display it
            st.session_state.query_result = results_payload

# --- Display Area for Results ---
if st.session_state.query_result:
    st.divider()
    st.subheader("Query Results")
    
    result = st.session_state.query_result
    plan = result["plan"]
    
    # Use an expander to neatly show the technical details
    with st.expander("Show Query Analysis and Execution Plan", expanded=False):
        st.write("**Analysis:**", plan.get("analysis", "N/A"))
        st.write("**DB1 SQL Query (Weather & Soil):**")
        st.code(plan.get("db1_sql", "N/A"), language="sql")
        st.write("**DB2 SQL Query (Crop Yields):**")
        st.code(plan.get("db2_sql", "N/A"), language="sql")
        st.write("**LLM Prompt (Advice & Recommendations):**")
        st.info(plan.get("llm_prompt", "N/A"))
        
    # Display the fetched dataframes
    if result["db1_data"] is not None:
        st.write("#### Data from DB1 (Weather & Soil)")
        st.dataframe(result["db1_data"])
        
    if result["db2_data"] is not None:
        st.write("#### Data from DB2 (Crop Yields)")
        st.dataframe(result["db2_data"])
