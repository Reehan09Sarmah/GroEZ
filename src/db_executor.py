import mysql.connector
import requests  # We need this library to make web requests
import json


def execute_db1_query(config: dict, query: str):
    """
    Connects to the DB1 MySQL database, executes a given query,
    and returns the results.
    """
    try:
        connection = mysql.connector.connect(
            host=config.get("host", "localhost"),
            user=config["user"],
            password=config["password"],
            database=config["database"],
            port=config.get("port", 3306),
        )
        if connection.is_connected():
            print("--> Successfully connected to DB1.")
            cursor = connection.cursor()
            cursor.execute(query)

            results = cursor.fetchall()
            column_names = [i[0] for i in cursor.description]

            cursor.close()
            connection.close()
            print("--> Connection to DB1 closed.")
            return results, column_names

    except mysql.connector.Error as e:
        print(f"Error connecting to or executing query on DB1: {e}")
        return None, None

    return None, None


def execute_db2_query_via_api(api_url: str, query: str):
    """
    Sends a SQL query to the DB2 Flask API and returns the results.

    Args:
        api_url (str): The URL of the Flask API endpoint (e.g., http://127.0.0.1:5000/query).
        query (str): The SQL query string to execute.

    Returns:
        list: A list of tuples/lists representing the rows fetched, or None on error.
        list: The column headers, or None on error.
    """
    try:
        payload = {"sql_query": query}
        # The timeout is set to 10 seconds to avoid waiting forever
        response = requests.post(api_url, json=payload, timeout=10)

        # Check if the request was successful (HTTP status code 200)
        if response.status_code == 200:
            data = response.json()
            # The API returns lists, not tuples, so we just return them as is.
            return data.get("data"), data.get("columns")
        else:
            print(
                f"Error from DB2 API: Status Code {response.status_code}, Response: {response.text}"
            )
            return None, None

    except requests.exceptions.RequestException as e:
        print(f"Failed to connect to the DB2 API: {e}")
        return None, None
