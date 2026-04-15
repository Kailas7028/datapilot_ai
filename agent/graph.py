from langgraph.graph import StateGraph, START, END
from agent.state import AgentState
from agent.nodes import sql_generation_node, sql_validation_node, sql_execution_node, retriever_node, result_summarization_node, visualization_recommender_node, chat_node, router_master
from langgraph.checkpoint.memory import MemorySaver

#should call sunnary agent
def should_call(state: AgentState) -> bool:
    """
    Node to determine if we should call the summary agent based on the result length
    """
    if state.get('result') and len(state['result']) > 100:  # Arbitrary length threshold
        return "end_workflow"
    return "summary_agent"

#routing function
def route_query(state:AgentState) -> str:
    if str(state.get("router_decision")) == "chat":
        return "chat_node"
    return "retriever"


# Define the graph structure
workflow = StateGraph(AgentState)

# CORRECT SYNTAX: "node_name", node_function
workflow.add_node("retriever", retriever_node)
workflow.add_node("sql_generation", sql_generation_node)
workflow.add_node("sql_validation", sql_validation_node)   
workflow.add_node("sql_execution", sql_execution_node)
workflow.add_node("summary_agent", result_summarization_node)
workflow.add_node("viz_node",visualization_recommender_node)
workflow.add_node("chat_node",chat_node)
workflow.add_node("router",router_master)
# workflow.add_node("retry", retry_node)

# Your edges remain exactly the same
workflow.set_entry_point("router")
workflow.add_conditional_edges(
    "router",
    route_query,
    {
        "chat_node": "chat_node",
        "retriever" : "retriever"
    }
)
workflow.add_edge("chat_node", END)
workflow.add_edge("retriever", "sql_generation")
workflow.add_edge("sql_generation", "sql_validation")
workflow.add_edge("sql_validation","sql_execution")

workflow.add_conditional_edges(
    "sql_execution",
    should_call,
    {
        "summary_agent": "summary_agent",
        "end_workflow" : END
    }
    )
workflow.add_edge("summary_agent", END)
# workflow.add_edge("summary_agent", "viz_node")
# workflow.add_edge("viz_node",END)

memory = MemorySaver()

app = workflow.compile(checkpointer=memory)