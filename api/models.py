from pydantic import BaseModel, Field
from typing import Optional, Any, Literal, List
# Define Pydantic models for request and response validation
class QueryRequest(BaseModel):
    question: str
    thread_id: Optional[str] = None  # Optional thread ID for tracing/logging

class QueryResponse(BaseModel):
    question: str
    generated_sql: Optional[str] = None
    result: Optional[Any] = None
    result_summary: Optional[str] = None
    viz_config: Optional[dict]
    
#visualization config model for the llm response to bind to a structured format

class ChartConfig(BaseModel):
    chart_id: Optional[str] = Field(description="Unique identifier for the chart (e.g., 'v1')")
    chart_type: Literal["bar", "line", "pie", "scatter", "area"] = Field(description="The type of Plotly chart")
    x_axis: Optional[str] = Field(description="Column name for the X-axis (leave null for pie charts)")
    y_axis: Optional[str] = Field(description="Column name for the Y-axis (or value column for pie charts)")
    title: Optional[str] = Field(description="A clean, human-readable title for the graph")
    description: Optional[str] = Field(description="A short explanation of what this chart reveals")
    is_primary: Optional[bool] = Field(description="Set to true for the single best chart, false for the others")
    color_column: Optional[str] = Field(default=None, description="Column name for grouping/coloring (e.g., category, city, or product name). Use when comparing multiple entities over time or categories.")

class VisualizationConfig(BaseModel):
    suggested_visualizations: List[ChartConfig] = Field(description="List of 1 to 3 visualization options")


# 1. The Pydantic Model for the Router LLM
class RouteDecision(BaseModel):
    decision: Literal["chat", "analytics"] = Field(
        description="Route to 'chat' for greetings or general questions. Route to 'analytics' for data, reports, or database queries."
    )

# Pydantic Model for Summrizer
class DataInsights(BaseModel):
    summary : str = Field(description="A brief 1-2 sentence conversational answer to the user's question.")
    key_insights: List[str] = Field(description="Exactly 3 bullet points highlighting trends, anomalies, or statistical facts from the data.")