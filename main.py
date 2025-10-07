import json
import getpass
from src.decomposer import QueryDecomposer
from src.db_executor import execute_db1_query  # Import the new function

# --- Configuration ---
DB1_CONFIG = {
    "user": "groez_user",
    "password": "groez09",
    "host": "localhost",
    "port": 3306,
    "database": "groez_db1",
}


def demonstrate_decomposer_and_executor():
    """
    Demonstrates the full flow:
    1. Decomposes a user query.
    2. Executes the generated SQL query for DB1.
    3. Prints both the plan and the fetched data.
    """
    print("--- Smart Agriculture System: Decompose & Execute Test ---")

    # 1. Securely get the API key
    try:
        api_key = getpass.getpass("Please enter your Google AI Studio API key: ")
        if not api_key:
            print("API key cannot be empty.")
            return
    except Exception as e:
        print(f"Could not read API key: {e}")
        return

    # 2. Initialize the decomposer
    try:
        decomposer = QueryDecomposer(api_key=api_key)
    except Exception as e:
        print(f"Failed to initialize the decomposer. Check your API key. Error: {e}")
        return

    # 3. Define test queries
    queries_to_test = [
        # This query should only use DB1
        "What is the average soil pH in Maharashtra?",
        # This query uses both, but we'll only execute the DB1 part for now
        "In Punjab, what is the best crop for sandy loam soil?",
    ]

    # 4. Run the tests
    for i, query in enumerate(queries_to_test):
        print("\n" + "=" * 50)
        print(f"Test Case #{i + 1}")

        decomposed_plan = decomposer.decompose(query)

        print("\n--- Decomposed Plan (JSON Output) ---")
        if "error" in decomposed_plan:
            print(f"An error occurred during decomposition: {decomposed_plan['error']}")
            continue

        print(json.dumps(decomposed_plan, indent=2))

        # --- NEW: EXECUTION STEP FOR DB1 ---
        db1_sql = decomposed_plan.get("db1_sql")

        if db1_sql and db1_sql != "N/A":
            print("\n--- Executing Query on DB1 ---")
            print(f"SQL: {db1_sql}")

            results, columns = execute_db1_query(DB1_CONFIG, db1_sql)

            if results is not None:
                print("\n--- DB1 Results ---")
                if results:
                    print(f"Columns: {columns}")
                    for row in results:
                        print(f"Data: {row}")
                else:
                    print("Query executed successfully, but returned no results.")
            else:
                print("Failed to retrieve results from DB1.")
        else:
            print("\n--- No query to execute on DB1 for this test case. ---")

        print("=" * 50)


if __name__ == "__main__":
    demonstrate_decomposer_and_executor()
