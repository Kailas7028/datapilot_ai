import os
import time
import asyncio
import asyncpg
from cryptography.fernet import Fernet
from dotenv import load_dotenv
from utils.loggers import get_logger
import app.central_db as central_db

logger = get_logger(__name__)
load_dotenv()

# Global Cache: { "org_123": {"pool": asyncpg.Pool, "last_accessed": 1690000000} }
tenant_pools = {} 

ENCRYPTION_KEY = os.getenv("MASTER_ENCRYPTION_KEY")
if not ENCRYPTION_KEY:
    raise ValueError("CRITICAL: MASTER_ENCRYPTION_KEY is missing from .env!")
cipher_suite = Fernet(ENCRYPTION_KEY.encode())

# --- CORE CONNECTION LOGIC ---

async def get_tenant_pool(org_id: str):
    """Returns the asyncpg pool for a specific organization, building it if necessary."""
    current_time = time.time()
    
    # CACHE HIT
    if org_id in tenant_pools:
        tenant_pools[org_id]["last_accessed"] = current_time
        return tenant_pools[org_id]["pool"]
        
    # CACHE MISS
    logger.info(f"Cache miss. Building new async connection pool for org: {org_id}")
    
    # Grab a connection from the central pool to fetch the URL
    async with central_db.central_pool.acquire() as central_conn:
        # asyncpg uses $1 instead of %s for parameters
        row = await central_conn.fetchrow(
            "SELECT encrypted_db_url FROM voxel_admin.tenant_databases WHERE org_id = $1", 
            org_id
        )
        
    if not row or not row['encrypted_db_url']:
        raise ValueError(f"No database configured for organization {org_id}")
        
    encrypted_url = row['encrypted_db_url']
    
    # AES-256 Decryption in RAM
    raw_db_url = cipher_suite.decrypt(encrypted_url.encode()).decode()
    
    # Build the async pool for this specific client
    try:
        new_pool = await asyncpg.create_pool(
            dsn=raw_db_url,
            min_size=1, 
            max_size=5,
            statement_cache_size=0
        )
        
        tenant_pools[org_id] = {
            "pool": new_pool,
            "last_accessed": current_time
        }
        
        return new_pool
    except Exception as e:
        logger.error(f"Failed to build async tenant pool for {org_id}: {e}")
        raise e

# --- THE TTL SWEEPER ---

async def sweep_idle_pools(idle_timeout_seconds=1800): 
    """Background task to close client async pools that have been idle."""
    while True:
        await asyncio.sleep(600)  # Check every 10 minutes
        current_time = time.time()
        stale_orgs = []
        
        for org_id, pool_data in tenant_pools.items():
            if (current_time - pool_data["last_accessed"]) > idle_timeout_seconds:
                stale_orgs.append(org_id)
                
        for org_id in stale_orgs:
            logger.info(f"Sweeping idle async connection pool for org: {org_id}")
            try:
                pool_to_close = tenant_pools[org_id]["pool"]
                await pool_to_close.close()
                del tenant_pools[org_id]
            except Exception as e:
                logger.error(f"Error sweeping pool for org {org_id}: {e}")