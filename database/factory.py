import os
from .base import BaseDatabase
from .postgres import PostgresDatabase
# from .sqlite import SQLiteDatabase

def get_database() -> BaseDatabase:
    """Factory method to get the active database instance."""
    db_type = os.getenv("DB_TYPE", "postgres") # Default to postgres
    db_url = os.getenv("DATABASE_URL")
    
    if not db_url:
        raise ValueError("CRITICAL: DATABASE_URL is missing from environment.")

    if db_type == "postgres":
        return PostgresDatabase(connection_url=db_url)
    # elif db_type == "sqlite":
    #     return SQLiteDatabase(connection_url=db_url)
    else:
        raise ValueError(f"Unsupported database type: {db_type}")