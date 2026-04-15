from typing import TypedDict, Optional, List

class AgentState(TypedDict):
    question: str
    retrieved_docs: Optional[List]
    generated_sql: Optional[str]
    validated_sql: Optional[str]
    result: Optional[list]
    error: Optional[str]
    retries: int
    input_tokens: int
    output_tokens: int
    result_summary: Optional[str]
    viz_config: Optional[dict]
    router_decision : Optional[str]
    data_insights: Optional[List[str]]