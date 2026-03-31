from pydantic import BaseModel
from typing import Optional, Any
# Define Pydantic models for request and response validation
class QueryRequest(BaseModel):
    question: str

class QueryResponse(BaseModel):
    question: str
    generated_sql: Optional[str] = None
    result: Optional[Any] = None