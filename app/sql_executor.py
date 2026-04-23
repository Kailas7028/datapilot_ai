from app.tenant_db import get_tenant_pool
from utils.loggers import get_logger

logger = get_logger(__name__)

async def execute_sql(sql: str, org_id: str) -> list:
    """
    Executes SQL against the specific organization's database using the async pool.
    """
    # Get the async pool for this specific organization
    pool = await get_tenant_pool(org_id)

    try:
        logger.info(f"Executing SQL for org {org_id}: {sql}")
        
        # 1. Acquire connection from the tenant's pool
        async with pool.acquire() as conn:
            
            # 2. Open a read-only transaction block for strict security
            async with conn.transaction(readonly=True):
                
                # 3. Fetch data directly. asyncpg returns a list of Record objects.
                records = await conn.fetch(sql)
                
                # 4. Convert Records to standard dicts for Streamlit/Pandas compatibility
                result = [dict(record) for record in records]
                
        return result
        
    except Exception as e:
        logger.error(f"Database execution failed: {e}")
        # The async with conn.transaction() block automatically rolled back the 
        # transaction the moment this exception was thrown.
        raise e