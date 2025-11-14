import json
import mysql.connector
from mysql.connector import Error
from src.decomposer import QueryDecomposer

# Import configs from your new centralized config file
from config import DB1_CONFIG, DB2_CONFIG, GEMINI_API_KEY


def execute_federated_query(db_config, query, db_name_label):
    """
    Executes a SQL query directly against a MySQL database using the provided config.
    Returns results and column names.
    """
    if not query or query == "N/A":
        return None, None

    connection = None
    try:
        connection = mysql.connector.connect(**db_config)
        if connection.is_connected():
            cursor = connection.cursor()
            cursor.execute(query)

            columns = (
                [col[0] for col in cursor.description] if cursor.description else []
            )
            results = cursor.fetchall()

            cursor.close()
            return results, columns

    except Error as e:
        print(f"❌ MySQL Error on {db_name_label}: {e}")
        return None, None
    finally:
        if connection and connection.is_connected():
            connection.close()


def demonstrate_full_federation():
    print("--- GroEZ: Full Federation Test (Direct DB Connections) ---")

    if not GEMINI_API_KEY:
        print("Error: GEMINI_API_KEY not found in .env file.")
        return

    try:
        decomposer = QueryDecomposer(
            api_key=GEMINI_API_KEY, db1_config=DB1_CONFIG, db2_config=DB2_CONFIG
        )
    except Exception as e:
        print(f"❌ Failed to initialize the decomposer: {e}")
        return

    queries_to_test = [
        "Compare the average Wheat yield in 2022 for districts with 'Alluvial' soil versus districts with 'Red' soil. Which soil type performed better and why might that be?",
        # "List the districts in Maharashtra where the average rainfall in 2023 was below 500mm. For these districts, what was the total production of Sugarcane, and suggest drought-resistant farming techniques.",
        # "Find districts with low soil nitrogen (< 150 ppm). What were the top 3 highest yielding crops in those districts in 2022, and what fertilizers would you recommend to improve nitrogen levels there?",
        # "In Punjab, for districts with alluvial soil, what was the Rice production in 2022?",
    ]

    for i, query in enumerate(queries_to_test):
        print("\n" + "#" * 70)
        print(f"Executing Test Case #{i + 1}")
        print(f"Query: '{query}'")
        print("#" * 70)

        try:
            decomposed_plan = decomposer.decompose(query)
        except Exception as e:
            print(f"❌ Decomposition failed: {e}")
            continue

        print("\n--- Decomposed Plan (JSON Output) ---")
        if "error" in decomposed_plan:
            print(f"Decomposition error: {decomposed_plan['error']}")
            continue

        print(json.dumps(decomposed_plan, indent=2))

        print("\n🏎️💨 STARTING FEDERATED EXECUTION ⬇️")

        results1, cols1 = execute_federated_query(
            DB1_CONFIG, decomposed_plan.get("db1_sql"), "DB1 (Local)"
        )
        if results1:
            print(f"✅ DB1 Results (Columns: {cols1}):")
            for row in results1:
                print(f"   {row}")

        results2, cols2 = execute_federated_query(
            DB2_CONFIG, decomposed_plan.get("db2_sql"), "DB2 (Remote)"
        )
        if results2:
            print(f"✅ DB2 Results (Columns: {cols2}):")
            for row in results2:
                print(f"   {row}")

        llm_prompt = decomposed_plan.get("llm_prompt")
        if llm_prompt and llm_prompt != "N/A":
            print("\n--- LLM Prompt Generated (Ready for Synthesis Phase) ---")
            print(f"Prompt: {llm_prompt}")

    print("\n" + "#" * 70)
    print("All test cases complete.")
    print("#" * 70)


if __name__ == "__main__":
    demonstrate_full_federation()
