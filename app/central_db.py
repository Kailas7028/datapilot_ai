import os
import asyncpg
from dotenv import load_dotenv
from utils.loggers import get_logger

logger = get_logger(__name__)
load_dotenv()

DATABASE_URL = os.getenv("SUPABASE_URL")
if not DATABASE_URL:
    raise ValueError("CRITICAL: SUPABASE_URL environment variable is missing!")

# Global variable to hold the pool
central_pool = None

async def init_central_pool():
    """Initializes the central asyncpg connection pool on server startup."""
    global central_pool
    try:
        central_pool = await asyncpg.create_pool(
            dsn=DATABASE_URL,
            min_size=1,
            max_size=20,
            statement_cache_size=0  # Disable asyncpg's internal statement caching 
        )
        logger.info("Central DB async connection pool created successfully.")
    except Exception as e:
        logger.error(f"Error creating central async connection pool: {e}")
        raise e

async def close_central_pool():
    """Closes the central pool gracefully on server shutdown."""
    global central_pool
    if central_pool:
        await central_pool.close()
        logger.info("Central DB async connection pool closed.")