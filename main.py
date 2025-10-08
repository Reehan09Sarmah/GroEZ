import json
import getpass
import requests  # <-- Make sure this library is installed
from src.decomposer import QueryDecomposer
from src.db_executor import (
    execute_db1_query,
    execute_db2_query_via_api,
)  # Import both functions

# --- Configuration ---
DB1_CONFIG = {
    "user": "groez_user",
    "password": "groez09",
    "host": "localhost",
    "port": 3306,
    "database": "groez_db1",
}

# The URL for your partner's running Flask API server.
# Make sure this is updated with your partner's actual local network IP address.
DB2_API_URL = (
    "http://192.168.52.99:5000/query"  # <--- IMPORTANT: REPLACE WITH PARTNER'S IP
)


def demonstrate_full_federation():
    """
    Demonstrates the complete flow with multiple test cases:
    1. Decomposes each user query.
    2. Executes queries on DB1 (direct connection) and DB2 (via API).
    3. Prints all results for each case.
    """
    print("--- Smart Agriculture System: Full Federation Test ---")

    # 1. Get Gemini API Key
    api_key = getpass.getpass("Please enter your Google AI Studio API key: ")
    if not api_key:
        print("API key cannot be empty.")
        return

    # 2. Initialize Decomposer
    try:
        decomposer = QueryDecomposer(api_key=api_key)
    except Exception as e:
        print(f"Failed to initialize the decomposer: {e}")
        return

    # 3. Define a list of diverse test queries
    queries_to_test = [
        # Test Case 1: Primarily DB2 (Production Info)
        "What was the total production of Sugarcane in Maharashtra in 2023?",
        # Test Case 4: Simple Aggregate on DB2
        "List the top 3 crops with the highest average yield across all years in Punjab.",
    ]

    for i, query in enumerate(queries_to_test):
        print("\n" + "#" * 70)
        print(f"Executing Test Case #{i + 1}")
        print(f"Query: '{query}'")
        print("#" * 70)

        decomposed_plan = decomposer.decompose(query)

        print("\n--- Decomposed Plan (JSON Output) ---")
        if "error" in decomposed_plan:
            print(f"Decomposition error: {decomposed_plan['error']}")
            continue  # Skip to the next query

        print(json.dumps(decomposed_plan, indent=2))

        # --- EXECUTION STEP FOR DB1 ---
        db1_sql = decomposed_plan.get("db1_sql")
        if db1_sql and db1_sql != "N/A":
            print("\n--- Executing Query on DB1 (Local) ---")
            results, columns = execute_db1_query(DB1_CONFIG, db1_sql)
            if results is not None:
                print("\n--- DB1 Results ---")
                print(f"Columns: {columns}")
                for row in results:
                    print(f"Data: {row}")
            else:
                print("Failed to get results from DB1.")
        else:
            print("\n--- No query for DB1. ---")

        # --- EXECUTION STEP FOR DB2 ---
        db2_sql = decomposed_plan.get("db2_sql")
        if db2_sql and db2_sql != "N/A":
            print("\n--- Executing Query on DB2 (via API) ---")
            results, columns = execute_db2_query_via_api(DB2_API_URL, db2_sql)
            if results is not None:
                print("\n--- DB2 Results ---")
                print(f"Columns: {columns}")
                for row in results:
                    print(f"Data: {row}")
            else:
                print(
                    "Failed to get results from DB2. Ensure the API server is running."
                )
        else:
            print("\n--- No query for DB2. ---")

        # We will add the LLM execution step in a later phase
        llm_prompt = decomposed_plan.get("llm_prompt")
        if llm_prompt and llm_prompt != "N/A":
            print("\n--- LLM Prompt Generated (Execution in Phase 4) ---")
            print(f"Prompt: {llm_prompt}")

    print("\n" + "#" * 70)
    print("All test cases complete.")
    print("#" * 70)


if __name__ == "__main__":
    demonstrate_full_federation()
