import os
import psycopg2
from dotenv import load_dotenv
from utils.loggers import get_logger
logger = get_logger(__name__)


# 1. Load the secure variables from your .env file
load_dotenv()

# 2. Grab the Supabase URL
DATABASE_URL = os.getenv("SUPABASE_URL")
if not DATABASE_URL:
    raise ValueError("CRITICAL: SUPABASE_URL environment variable is missing!")

def get_connection():
    """
    Creates a fresh connection to the Supabase cloud database.
    Your nodes.py will still call this exact same function!
    """
    try:
        # psycopg2 is smart enough to connect directly using the URL string
        return psycopg2.connect(DATABASE_URL)
    except Exception as e:
        logger.error(f"Failed to connect to the database: {e}")
        raise e