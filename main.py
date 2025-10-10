import json
import os
from dotenv import load_dotenv
import getpass
import requests
from src.decomposer import QueryDecomposer
from src.db_executor import (
    execute_db1_query,
    execute_db2_query_via_api,
)

# --- Configuration ---
DB1_CONFIG = {
    "user": "groez_user",
    "password": "groez09",
    "host": "localhost",
    "port": 3306,
    "database": "groez_db1",
}

DB2_API_URL = "http://192.168.52.99:5000/query"


script_dir = os.path.dirname(__file__)
env_path = os.path.join(script_dir, ".env")
load_dotenv(dotenv_path=env_path)


def demonstrate_full_federation():
    print("--- GroEZ: Full Federation Test ---")

    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("Error: GEMINI_API_KEY not found.")
        print(
            "Please ensure you have a .env file in the project root with your API key."
        )
        return

    # 2. Initialize Decomposer
    try:
        decomposer = QueryDecomposer(api_key=api_key)
    except Exception as e:
        print(f"Failed to initialize the decomposer: {e}")
        return

    queries_to_test = [
        "What was the total production of Sugarcane in Maharashtra in 2023?",
        "In Punjab, for districts with alluvial soil, what was the total production of Rice in 2022, and what are the best fertilization practices for Rice in that type of soil?",
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
            continue

        print(json.dumps(decomposed_plan, indent=2))

        # print("Now let us execute the queries on DB1 and DB2")
        # db1_sql = decomposed_plan.get("db1_sql")
        # if db1_sql and db1_sql != "N/A":
        #     print("\n--- Executing Query on DB1 (Local) ---")
        #     results, columns = execute_db1_query(DB1_CONFIG, db1_sql)
        #     if results is not None:
        #         print("\n--- DB1 Results ---")
        #         print(f"Columns: {columns}")
        #         for row in results:
        #             print(f"Data: {row}")
        #     else:
        #         print("Failed to get results from DB1.")
        # else:
        #     print("\n--- No query for DB1. ---")

        # db2_sql = decomposed_plan.get("db2_sql")
        # if db2_sql and db2_sql != "N/A":
        #     print("\n--- Executing Query on DB2 (via API) ---")
        #     results, columns = execute_db2_query_via_api(DB2_API_URL, db2_sql)
        #     if results is not None:
        #         print("\n--- DB2 Results ---")
        #         print(f"Columns: {columns}")
        #         for row in results:
        #             print(f"Data: {row}")
        #     else:
        #         print(
        #             "Failed to get results from DB2. Ensure the API server is running."
        #         )
        # else:
        #     print("\n--- No query for DB2. ---")

        # llm_prompt = decomposed_plan.get("llm_prompt")
        # if llm_prompt and llm_prompt != "N/A":
        #     print("\n--- LLM Prompt Generated (Execution in Phase 4) ---")
        #     print(f"Prompt: {llm_prompt}")

    print("\n" + "#" * 70)
    print("All test cases complete.")
    print("#" * 70)


if __name__ == "__main__":
    demonstrate_full_federation()
