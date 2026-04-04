from langgraph.graph import StateGraph, START, END
from agent.state import AgentState
from agent.nodes import sql_generation_node, sql_validation_node, sql_execution_node, retriever_node, result_summarization_node


#should call sunnary agent
def should_call(state: AgentState) -> bool:
    """
    Node to determine if we should call the summary agent based on the result length
    """
    if state.get('result') and len(state['result']) > 1000:  # Arbitrary length threshold
        return END
    return "summary_agent"


# Define the graph structure
workflow = StateGraph(AgentState)

# CORRECT SYNTAX: "node_name", node_function
workflow.add_node("retriever", retriever_node)
workflow.add_node("sql_generation", sql_generation_node)
workflow.add_node("sql_validation", sql_validation_node)   
workflow.add_node("sql_execution", sql_execution_node)
workflow.add_node("summary_agent", result_summarization_node)
# workflow.add_node("retry", retry_node)

# Your edges remain exactly the same
workflow.add_edge(START, "retriever")
workflow.add_edge("retriever", "sql_generation")
workflow.add_edge("sql_generation", "sql_validation")
workflow.add_edge("sql_validation","sql_execution")
workflow.add_conditional_edges("sql_execution",should_call)
workflow.add_edge("summary_agent", END)


app = workflow.compile()