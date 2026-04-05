# api/auth.py
from datetime import datetime, timedelta
from typing import Optional
import jwt
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel
import uuid
from utils.loggers import  user_id_var
from app.db import get_connection  # Import your existing DB connection!

# --- Configuration ---
SECRET_KEY = "your-super-secret-key-change-this-in-production"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 15

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/v1/login")

# --- Utility Functions ---
def get_password_hash(password):
    return pwd_context.hash(password)

def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    expire = datetime.now() + (expires_delta if expires_delta else timedelta(minutes=15))
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

# --- Dependency to Protect Routes ---
async def get_current_user(token: str = Depends(oauth2_scheme)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str = payload.get("sub")

            # Set the user_id in the context variable for logging
        user_id_var.set(user_id)
        if user_id is None:
            raise credentials_exception
        return {"user_id": user_id}  # You can expand this to include more user info if needed
    except jwt.PyJWTError:
        raise credentials_exception
        
    # user = get_user_from_db(username) # Now checking the real database!
    # if user is None:
    #     raise credentials_exception
    # return user



# --- Database Helper Functions ---
def get_user_from_db(email: str):
    """Fetches a user from your existing PostgreSQL table."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        # Update 'your_table_name' and ensure column names match your DB
        # Assuming column 3 is named 'email'
        cursor.execute("SELECT id, email, password_hash FROM users WHERE email = %s;", (email,))
        row = cursor.fetchone()
        
        if row and row[2]: # Ensure the user actually has a password set!
            return {"id": row[0], "username": row[1], "hashed_password": row[2]}
        return None
    finally:
        cursor.close()
        conn.close()

def create_user_in_db(email: str, hashed_password: str):
    """Inserts a new user into your existing PostgreSQL table."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        # Generate a new UUID for Column 1
        new_id = str(uuid.uuid4())
        signup_date = datetime.now()
        
        # You will need to provide default values for the other required columns!
        # For example, defaulting role to 'member', country to 'Unknown', etc.
        cursor.execute(
            """
            INSERT INTO users 
            (id, email, password_hash, is_active,signup_date) 
            VALUES (%s, %s, %s, true, %s);
            """,
            (new_id, email, hashed_password, signup_date)
        )
        conn.commit()
        return True
    except Exception as e:
        print(f"DB Error: {e}") # Helpful for debugging
        conn.rollback()
        return False
    finally:
        cursor.close()
        conn.close()