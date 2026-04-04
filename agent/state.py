from typing import TypedDict, Optional

class AgentState(TypedDict):
    question: str
    retrieved_docs: Optional[list]
    generated_sql: Optional[str]
    validated_sql: Optional[str]
    result: Optional[str]
    error: Optional[str]
    retries: int
    input_tokens: int
    output_tokens: int
    result_summary: Optional[str]