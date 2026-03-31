from langgraph.graph import StateGraph, START, END
from agent.state import AgentState
from agent.nodes import sql_generation_node, sql_validation_node, sql_execution_node, retriever_node


# #route method for the graph
# def should_retry(state: AgentState) -> str:
#     if state['error'] and state['retries'] < 1:
#         return "retry"
#     if state["error"] and state["retries"] >= 1:
#         return END
#     return "execute"

# Define the graph structure
workflow = StateGraph(AgentState)

# CORRECT SYNTAX: "node_name", node_function
workflow.add_node("retriever", retriever_node)
workflow.add_node("sql_generation", sql_generation_node)
workflow.add_node("sql_validation", sql_validation_node)   
workflow.add_node("sql_execution", sql_execution_node)
# workflow.add_node("retry", retry_node)

# Your edges remain exactly the same
workflow.add_edge(START, "retriever")
workflow.add_edge("retriever", "sql_generation")
workflow.add_edge("sql_generation", "sql_validation")

# workflow.add_conditional_edges(
#     "sql_validation",
#     should_retry,
#     {
#         "execute": "sql_execution",
#         "retry": "retry",
#         END: END
#     }
# )

# workflow.add_edge("retry", "sql_validation")
workflow.add_edge("sql_validation","sql_execution")
workflow.add_edge("sql_execution", END)

app = workflow.compile()