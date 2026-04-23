import os
import re
import uuid
import jwt
from datetime import datetime, timedelta
from pydantic import BaseModel
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from passlib.context import CryptContext

# Import your async central pool
import app.central_db as central_db
from utils.loggers import user_id_var, org_id_var

# Security configs (Keep your existing values)
SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/v1/login")

# --- PYDANTIC MODELS ---
class UserCreate(BaseModel):
    username: str
    password: str
    company_name: str  # Required to generate the org_id

# --- HELPER FUNCTIONS ---
def get_password_hash(password):
    return pwd_context.hash(password)

def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)
#------------------------------------------------------------------
def create_access_token(data: dict, expires_delta: timedelta = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt
#------------------------------------------------------------
def generate_org_id(company_name: str) -> str:
    """Generates a readable ID like 'org_acmecorp_a1b2'"""
    clean_name = re.sub(r'[^a-z0-9]', '', company_name.lower())[:15]
    if not clean_name:
        clean_name = "tenant"
    short_hash = uuid.uuid4().hex[:4]
    return f"org_{clean_name}_{short_hash}"


#----------------------------------------------------
# --- ASYNC DATABASE FUNCTIONS ---
#-----------------------------------------------------
async def get_user_from_db(email: str):
    """Fetches user and org_id from the secure voxel_admin schema."""
    try:
        async with central_db.central_pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT id, org_id, email, password_hash, role FROM voxel_admin.users WHERE email = $1", 
                email
            )
            if row and row["password_hash"]:
                return {
                    "id": str(row["id"]), 
                    "org_id": row["org_id"],  # This is already a string
                    "email": row["email"], 
                    "hashed_password": row["password_hash"],
                    "role": row["role"]
                }
            return None
    except Exception as e:
        print(f"DB Fetch Error: {e}")
        return None
#------------------------------------------------------------------------------
# Create User with Organization in one transaction, grouping by existing company names
#------------------------------------------------------------------------------

async def create_user_in_db(email: str, hashed_password: str, company_name: str):
    """Creates Organization and User in one async transaction, grouping existing companies."""
    try:
        async with central_db.central_pool.acquire() as conn:
            async with conn.transaction():
                
                # 1. Check if the organization already exists
                existing_org_id = await conn.fetchval(
                    "SELECT id FROM voxel_admin.organizations WHERE name = $1",
                    company_name
                )

                if existing_org_id:
                    # Use the existing ID so they share the database and RAG context
                    org_id = existing_org_id
                else:
                    # Generate a new ID and insert the new organization
                    org_id = generate_org_id(company_name)
                    await conn.execute(
                        "INSERT INTO voxel_admin.organizations (id, name) VALUES ($1, $2)",
                        org_id, company_name
                    )
                
                # 2. Create the User linked to the resolved org_id
                await conn.execute(
                    """
                    INSERT INTO voxel_admin.users (org_id, email, password_hash) 
                    VALUES ($1, $2, $3)
                    """,
                    org_id, email, hashed_password
                )
                return org_id
    except Exception as e:
        print(f"DB Registration Error: {e}")
        return None
    


#---------------------------------------------------------------------
# --- FASTAPI DEPENDENCY ---
#---------------------------------------------------------------------
async def get_current_user(token: str = Depends(oauth2_scheme)):
    """Extracts user_id and org_id from the JWT token."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str = payload.get("sub")
        org_id: str = payload.get("org_id") 
        role: str = payload.get("role", "user")  # Default to 'user' if not present
        
        # Keep your central logger variable updated
        user_id_var.set(user_id)
        org_id_var.set(org_id)

        
        if user_id is None or org_id is None:
            raise credentials_exception
            
        return {"user_id": user_id, "org_id": org_id, "role": role} 
        
    except jwt.PyJWTError:
        raise credentials_exception
#------------------------------------------------------
# SUPERADMIN PROVISIONING LOCK
# ------------------------------------------------------   
async def require_admin(current_user: dict = Depends(get_current_user)):
    """Dependency to lock down routes to organization admins only."""
    if current_user.get("role") != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, 
            detail="Unauthorized. Organization Admin access required."
        )
    return current_user