import os
import json
import time
import uuid
import asyncio
from datetime import timedelta
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, Depends, HTTPException, status, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.responses import StreamingResponse
from cryptography.fernet import Fernet
from dotenv import load_dotenv
#rate limiting
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

# Import auth functions
from api.auth import (
    UserCreate, get_user_from_db, create_user_in_db, get_password_hash,
    verify_password, create_access_token, get_current_user, ACCESS_TOKEN_EXPIRE_MINUTES, require_admin
)

# Import DB, Agent, and Loggers
from app.central_db import init_central_pool, close_central_pool, central_pool
import app.central_db as central_db
from app.tenant_db import sweep_idle_pools
from agent.agent import run_agent
from api.models import QueryRequest, DatabaseUpdateRequest
from utils.loggers import get_logger, request_id_var, user_id_var, org_id_var
from rag.Indexer import SchemaIndexer

logger = get_logger(__name__)
load_dotenv()
indexer = SchemaIndexer()

# --- 1. APP LIFESPAN ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_central_pool()
    sweeper_task = asyncio.create_task(sweep_idle_pools(idle_timeout_seconds=1800))
    logger.info("Voxel Backend Started: Pools initialized.")
    yield
    sweeper_task.cancel()
    await close_central_pool()
    logger.info("Voxel Backend Shutdown: Pools closed.")

app = FastAPI(title="Voxel Multi-Tenant API", lifespan=lifespan)

# --- RATE LIMITER SETUP ---
limiter = Limiter(key_func=get_remote_address, default_limits=["1000/hour"])
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)
#------------------------------

# --- 2. RESTORED MIDDLEWARE (Observability & Tracking) ---
@app.middleware("http")
async def add_request_id_to_logs(request: Request, call_next):
    # Restore your unique request ID logic [cite: 74]
    request_id = str(uuid.uuid4())[:8]  
    token = request_id_var.set(request_id)
    
    start_time = time.perf_counter()
    try:
        response = await call_next(request)
        process_time = time.perf_counter() - start_time
        
        # Restore your Success/Failure logging [cite: 75, 76]
        if response.status_code >= 400:
            logger.error(
                f"API FAILURE: {request.method} {request.url.path} "
                f"- Status: {response.status_code} - Time: {process_time:.4f}s"
            )
        else:
            logger.info(
                f"API SUCCESS: {request.method} {request.url.path} "
                f"- Status: {response.status_code} - Time: {process_time:.4f}s"
            )
        return response
    finally:
        request_id_var.reset(token)

# Add CORS for Streamlit
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- 3. SUPER ADMIN & PROVISIONING ---
SUPERADMIN_KEY = os.getenv("VOXEL_SUPERADMIN_KEY")

async def verify_superadmin(x_admin_key: str = Header(...)):
    if not SUPERADMIN_KEY or x_admin_key != SUPERADMIN_KEY:
        raise HTTPException(status_code=403, detail="Unauthorized. Super Admin access required.")
    return True

#---------------------------------------------------------------
# PROVISION NEW TENANT (SUPER ADMIN ONLY)
#---------------------------------------------------------------
@app.post("/api/v1/admin/provision-tenant", status_code=201)
async def provision_new_tenant(user: UserCreate, is_admin: bool = Depends(verify_superadmin)):
    existing_user = await get_user_from_db(user.username)
    if existing_user:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    hashed_pwd = get_password_hash(user.password)
    org_id = await create_user_in_db(user.username, hashed_pwd, user.company_name) 
    
    if not org_id:
        raise HTTPException(status_code=500, detail="Failed to provision tenant")
        
    # --- THE FIX: Safe Demo Database Injection ---
    DEMO_DB_URL = os.getenv("DEMO_DATABASE_URL")
    MASTER_KEY = os.getenv("MASTER_ENCRYPTION_KEY")
    
    if DEMO_DB_URL and MASTER_KEY:
        try:
            cipher_suite = Fernet(MASTER_KEY.encode())
            encrypted_demo_url = cipher_suite.encrypt(DEMO_DB_URL.encode()).decode()
            async with central_db.central_pool.acquire() as conn:
                # Add ON CONFLICT DO NOTHING to prevent crashes for existing orgs
                await conn.execute(
                    """
                    INSERT INTO voxel_admin.tenant_databases (org_id, encrypted_db_url) 
                    VALUES ($1, $2)
                    ON CONFLICT (org_id) DO NOTHING
                    """,
                    org_id, encrypted_demo_url
                )
        except Exception as e:
            # We log the error but DO NOT raise an HTTPException, 
            # because the user was still successfully created!
            logger.error(f"Failed to inject demo DB for {org_id}: {e}")
            
    return {"message": f"Successfully provisioned {user.company_name}.", "org_id": org_id}


#--------------------------------------------------------------------------------------
# --- 4. AUTH & SETTINGS ---
@app.post("/api/v1/login")
@limiter.limit("5/minute")  # Limit login attempts to prevent brute-force attacks
async def login_for_access_token(request: Request, form_data: OAuth2PasswordRequestForm = Depends()):
    user = await get_user_from_db(form_data.username )
    if not user or not verify_password(form_data.password, user["hashed_password"]):
        raise HTTPException(status_code=401, detail="Incorrect username or password")
    user_id_var.set(user["id"])
    org_id_var.set(user["org_id"])
    access_token = create_access_token(
        data={"sub": user.get("id"), "org_id": user.get("org_id"), "role": user.get("role", "user")}, 
        expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    print(f"Debug Login: user {user['id']} from org {user['org_id']} with role {user.get('role', 'user')} logged in.")
    return {"access_token": access_token, "token_type": "bearer","role": user.get("role", "user")}
#-------------------------------------------------------------------------------------------
# Update Tenant Database URL (Authenticated Endpoint)
@app.put("/api/v1/settings/database")
@limiter.limit("5/hour")  # Limit to prevent abuse
async def update_tenant_database(request: Request, payload: DatabaseUpdateRequest, user: dict = Depends(require_admin)):
    org_id = user.get("org_id")
    MASTER_KEY = os.getenv("MASTER_ENCRYPTION_KEY")
    if not MASTER_KEY:
        logger.error("MASTER_ENCRYPTION_KEY missing from environment.")
        raise HTTPException(status_code=500, detail="Master encryption key not configured.")
    try:
        cipher_suite = Fernet(MASTER_KEY.encode())
        encrypted_url = cipher_suite.encrypt(payload.db_url.encode()).decode()

    except Exception as e:
        logger.error(f"Error occurred while encrypting database URL: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to encrypt database URL.")
    try:
        async with central_db.central_pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO voxel_admin.tenant_databases (org_id, encrypted_db_url) VALUES ($1, $2) "
                "ON CONFLICT (org_id) DO UPDATE SET encrypted_db_url = EXCLUDED.encrypted_db_url",
                org_id, encrypted_url
            )
    except Exception as e:
        logger.error(f"Database error while updating tenant database URL: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to update tenant database URL.")
    
    # 3. Clear Pool Cache so the next query uses the NEW URL
    from app.tenant_db import tenant_pools
    if org_id in tenant_pools:
        # Close the old pool properly
        try:
            await tenant_pools[org_id]["pool"].close()
        except:
            pass
        del tenant_pools[org_id]
    # Background indexing [cite: 336]
    asyncio.create_task(indexer.sync_schema_to_vectordb(org_id))
    return {"message": "Database updated and indexing started."}


#--------------------------------------------------------------------------------------
# --- 5. QUERY ENDPOINT ---
@app.post("/api/v1/query")
@limiter.limit("10/minute")  # Limit query requests to prevent abuse
async def ask_database(request: Request, payload: QueryRequest, user: dict = Depends(get_current_user)):
    org_id = user.get("org_id")
    user_id = user.get("user_id")

    async def event_generator():
        try:
            async for chunk in run_agent(payload.question, payload.thread_id, org_id, user_id):
                yield chunk
        except Exception as e:
            logger.error(f"Error in agent execution: {str(e)}")
            yield json.dumps({"error": "An error occurred while processing your request."}) + "\n"

    return StreamingResponse(event_generator(), media_type="application/x-ndjson")