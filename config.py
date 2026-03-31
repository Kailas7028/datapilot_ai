import os
from dotenv import load_dotenv

load_dotenv()

#Database connection configuration
DB_CONFIG = {
    "dbname": os.getenv("DATABASE_NAME"),
    "user": os.getenv("DB_USER"),
    "password": os.getenv("DB_PASSWORD"),
    "host": os.getenv("DB_HOST"),
    "port": os.getenv("DB_PORT")
}

# OpenAI API configuration
GROQ_API_KEY = os.getenv("GROQ_API_KEY")