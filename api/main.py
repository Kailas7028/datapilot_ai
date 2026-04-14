# from fastapi import FastAPI, HTTPException, Request
# from fastapi.middleware.cors import CORSMiddleware
# from api.models import QueryRequest, QueryResponse
# import uvicorn
# from agent.agent import run_agent
# from utils.loggers import get_logger, request_id_var
# import uuid
# import time
# logger = get_logger(__name__)



# # Initialize the FastAPI app
# app = FastAPI(
#     title="DataPilot AI Agent API",
#     description="Asynchronous API for the LangGraph SQL Generation Agent",
#     version="1.0.0"
# )

# # Add CORS middleware for frontend/external access
# app.add_middleware(
#     CORSMiddleware,
#     allow_origins=["*"],  # Update this to specific domains in production
#     allow_credentials=True,
#     allow_methods=["*"],
#     allow_headers=["*"],
# )

# # Middleware to set a unique request ID for each incoming request, which will be included in all log entries for better traceability.
# @app.middleware("http")
# async def add_request_id_to_logs(request:Request, call_next):
#     #generate a unique request ID (you can use uuid4 or any other method)
#     request_id = str(uuid.uuid4())[:8]  # Shorten the UUID for readability
#     # Set the request ID in the context variable for this request
#     token=request_id_var.set(request_id)

#     try:
#         start_time = time.perf_counter()
#         response = await call_next(request)
#         process_time = time.perf_counter() - start_time
#         logger.info(f"Request completed in {process_time:.2f} seconds")
#         return response
#     finally:        # Reset the context variable to avoid leaking the request ID into other requests
#         request_id_var.reset(token)

# #----------------------------------------------------------------------------------------------------------

# #root point
# @app.get("/")
# def health_check() -> str:
#     return "Hello world"


# #-----------------------------------------------------------------------------------------------------------

# # Create the async endpoint
# @app.post("/api/v1/query", response_model=QueryResponse)
# async def ask_database(payload: QueryRequest):
#     logger.info(f"Received query: {payload.question}")
#     try:
#         # Execute the LangGraph workflow
#         state_result = run_agent(payload.question)
        
        
#         # Map the AgentState dictionary to the Pydantic response model
#         return QueryResponse(
#             question=payload.question,
#             generated_sql=state_result.get("generated_sql"),
#             result=state_result.get("result")
#         )
        
#     except Exception as e:
#         # Catch any unexpected graph or database crashes
#         logger.error(f"Critical error API Failure: {str(e)}")
#         raise HTTPException(status_code=500, detail=f"Agent execution failed: {str(e)}")

# # Run the server
# if __name__ == "__main__":
#     uvicorn.run("api.main:app", host="0.0.0.0", port=8000, reload=True)



from fastapi import FastAPI, HTTPException, Request, Depends, status
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.middleware.cors import CORSMiddleware
from api.models import QueryRequest, QueryResponse
import uvicorn
from agent.agent import run_agent
from utils.loggers import get_logger, request_id_var, user_id_var
import uuid
import time
from datetime import timedelta
from api.auth import verify_password, create_access_token, get_current_user,ACCESS_TOKEN_EXPIRE_MINUTES, get_user_from_db, get_user_from_db, create_user_in_db, get_password_hash
from pydantic import BaseModel
import os
logger = get_logger(__name__)

# Initialize the FastAPI app
app = FastAPI(
    title="DataPilot AI Agent API",
    description="Asynchronous API for the LangGraph SQL Generation Agent",
    version="1.0.0"
)

# Add CORS middleware for frontend/external access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Update this to specific domains in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Middleware to set a unique request ID and log API Success/Failures
@app.middleware("http")
async def add_request_id_to_logs(request: Request, call_next):
    # Generate a unique request ID 
    request_id = str(uuid.uuid4())[:8]  
    
    # Set the request ID in the context variable for this request
    token = request_id_var.set(request_id)
    id = user_id_var.get()  # Get the user_id from the context variable (if set by auth)

    start_time = time.perf_counter()
    try:
        # Let the request process normally
        response = await call_next(request)
        process_time = time.perf_counter() - start_time
        
        # --- NEW OBSERVABILITY LOGIC ---
        # If the route doesn't exist (404) or the server crashed (500)
        if response.status_code >= 400:
            logger.error(
                f"API FAILURE: {request.method} {request.url.path} "
                f"- Status: {response.status_code} - Time: {process_time:.4f}s"
            )
        else:
            # Log successful requests
            logger.info(
                f"API SUCCESS: {request.method} {request.url.path} "
                f"- Status: {response.status_code} - Time: {process_time:.4f}s"
            )

        return response
        
    finally:
        # Reset the context variable to avoid leaking the request ID
        request_id_var.reset(token)

#----------------------------------------------------------------------------------------------------------

# Root point
@app.get("/")
def health_check() -> str:
    return "Hello world"

#-----------------------------------------------------------------------------------------------------------

# Pydantic model for incoming registration data
class UserCreate(BaseModel):
    username: str
    password: str

@app.post("/api/v1/register", status_code=201)
async def register_user(user: UserCreate):
    # 1. Check if user already exists
    existing_user = get_user_from_db(user.username)
    if existing_user:
        raise HTTPException(status_code=400, detail="Username already registered")
    
    # 2. Hash the password
    hashed_pwd = get_password_hash(user.password)
    
    # 3. Save to database
    success = create_user_in_db(user.username, hashed_pwd)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to create user")
        
    return {"message": "User created successfully"}
#-----------------------------------------------------------------------------------------------------------

# 1. The Login Endpoint
@app.post("/api/v1/login")
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends()):
    # Now we query PostgreSQL instead of the fake dictionary
    user = get_user_from_db(form_data.username)
    
    if not user or not verify_password(form_data.password, user["hashed_password"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
        
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user["id"]}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}
#-----------------------------------------------------------------------------------------------------------

# Create the async endpoint
@app.post("/api/v1/query", response_model=QueryResponse)
async def ask_database(payload: QueryRequest, user: dict = Depends(get_current_user)):
    logger.info(f"Processig Query | Thread: {payload.thread_id} | question: {payload.question}")
    try:
        # Execute the LangGraph workflow
        state_result = await run_agent(payload.question, thread_id=payload.thread_id)
        # Map the AgentState dictionary to the Pydantic response model
        return QueryResponse(
            question=payload.question,
            generated_sql= state_result.get("generated_sql"),
            result= state_result.get("result"),
            result_summary= state_result.get("result_summary"),
            viz_config= state_result.get("viz_config")
        )
        
    except Exception as e:
        # Catch any unexpected graph or database crashes
        logger.error(f"Critical error API Failure: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Agent execution failed: {str(e)}")

# Run the server
if __name__ == "__main__":
    # Check if we are running in Render's cloud environment
    is_render = os.environ.get("RENDER") is not None
    
    # If in the cloud, open to the internet (0.0.0.0). 
    # If on your laptop, keep it safely restricted to localhost (127.0.0.1) to avoid Windows errors.
    host = "0.0.0.0" if is_render else "127.0.0.1"
    
    # Grab Render's dynamic port, or fallback to 8000 locally
    port = int(os.environ.get("PORT", 8000))
    
    uvicorn.run("api.main:app", host=host, port=port)