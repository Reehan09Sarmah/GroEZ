import os
from dotenv import load_dotenv


load_dotenv()


DB1_CONFIG = {
    "host": os.getenv("DB1_HOST"),
    "user": os.getenv("DB1_USER"),
    "password": os.getenv("DB1_PASSWORD"),
    "database": os.getenv("DB1_NAME"),
}


DB2_CONFIG = {
    "host": os.getenv("DB2_HOST"),
    "user": os.getenv("DB2_USER"),
    "password": os.getenv("DB2_PASSWORD"),
    "database": os.getenv("DB2_NAME"),
}


GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
