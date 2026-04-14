from app.db import get_connection, release_connection
import logging
from  psycopg2 import extras
logger = logging.getLogger(__name__)

def execute_sql(sql: str):
    
    # Get a connection from the pool
    conn = get_connection()
    
    # Set the connection to read-only mode to prevent any accidental writes
    conn.set_session(readonly=True, autocommit=True) 
    # Create a cursor for executing the SQL
    cursor = conn.cursor(cursor_factory=extras.RealDictCursor)

    try:
        logger.info(f"Executing SQL: {sql}")
        cursor.execute(sql)
        
        if cursor.description:  
            result = cursor.fetchall()
        else:
            result = []
        
    except Exception as e:
        logger.error(f"Database execution failed: {e}")
        # Rollback is still good practice to clear the failed transaction state
        conn.rollback() 
        raise e
    finally:
        #close the cursor and release the connection back to the pool
        if "cursor" in locals():
            cursor.close()
        release_connection(conn)

    return result