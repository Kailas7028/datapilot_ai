import os
from dotenv import load_dotenv
from utils.loggers import get_logger
from psycopg2 import pool
logger = get_logger(__name__)


# 1. Load the secure variables from your .env file
load_dotenv()

# 2. Grab the Supabase URL
DATABASE_URL = os.getenv("SUPABASE_URL")
if not DATABASE_URL:
    raise ValueError("CRITICAL: SUPABASE_URL environment variable is missing!")

try:
    # 3. Create a connection pool (optional but recommended for performance)
    connection_pool = pool.ThreadedConnectionPool(
        1, 20,  # min and max connections
        dsn=DATABASE_URL
    )
    if connection_pool:
        logger.info("Connection pool created successfully")

except Exception as e:
    logger.error(f"Error creating connection pool: {e}")
    raise e

def get_connection():
    """
    Get a connection from the pool
    """
    try:
        return connection_pool.getconn()
    except Exception as e:
        logger.error(f"Failed to get connection from pool: {e}")
        raise e
    

#Release the connection back to the pool after use
def release_connection(conn):
    """Returns connection back to pool

    Args:
        conn (_type_): connection object

    Raises:
        e: if failed to put the connection in pool
    """
    try:
        if conn:
            connection_pool.putconn(conn)
    except Exception as e:
        logger.error(f"Failed to release connection back to pool: {e}")
        raise e