import mysql.connector


def execute_db1_query(config: dict, query: str):
    """
    Connects to the DB1 MySQL database, executes a given query,
    and returns the results.

    Args:
        config (dict): A dictionary with db connection details
                       (user, password, host, database).
        query (str): The SQL query string to execute.

    Returns:
        list: A list of tuples representing the rows fetched, or None on error.
        list: The column headers, or None on error.
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

            # Fetch all results and column names
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
