from app.db import get_connection
import logging

logger = logging.getLogger(__name__)

def execute_sql(sql: str):
    # 1. First line of defense: String validation
    # This instantly blocks DROP, DELETE, UPDATE, INSERT before they even reach the DB.
    if not sql.strip().upper().startswith("SELECT"):
        raise ValueError("Security Alert: Only SELECT queries are permitted.")

    conn = get_connection()
    
    # 2. Second line of defense: Read-Only Transaction
    # If your driver supports it, force the database to reject writes.
    conn.set_session(readonly=True, autocommit=True) 
    
    cursor = conn.cursor()

    try:
        logger.info(f"Executing SQL: {sql}")
        cursor.execute(sql)
        
        # Since we enforced SELECT only, we know there will be a description
        if cursor.description:  
            result = cursor.fetchall()
        else:
            result = []

        # We REMOVED conn.commit() entirely. We are only reading!
        
    except Exception as e:
        logger.error(f"Database execution failed: {e}")
        # Rollback is still good practice to clear the failed transaction state
        conn.rollback() 
        raise e
    finally:
        cursor.close()
        conn.close()

    return result