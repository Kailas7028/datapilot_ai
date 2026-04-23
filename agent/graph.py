from langgraph.graph import StateGraph, START, END
from agent.state import AgentState
from agent.nodes import (sql_generation_node,
                         sql_validation_node,
                         sql_execution_node,
                         retriever_node,
                         result_summarization_node,
                         visualization_recommender_node,
                         chat_node,
                         router_master,
                         retry_node
                            )
from langgraph.checkpoint.memory import MemorySaver


# Condtional function to decide graph flow
def master_router(state: AgentState) -> str:
    router_decision = state.get("router_decision")
    if router_decision == 'chat':
        return 'chat'
    elif router_decision == 'analytics':
        return 'analytics'
    else:
        return 'analytics'  # default to retriever if no decision or unrecognized decision
    

# Post router after sql validation
# 2. Validation Router (CRITICAL FIX)
def post_validation_router(state: AgentState) -> str:
    if state.get("error"):
        if state.get("retries", 0) < 2:
            return 'retry_node'
        return END  # Out of retries, end the flow safely
    return 'sql_execution'
    
# conditions after sql execution route to summary or not and route to retry or not
def post_execution_router(state: AgentState) -> str:
    # 1. If there is an error, handle the retry loop
    if state.get("error"):
        if state.get("retries", 0) < 2:  # Retry up to 2 times
            return 'retry_node'
        return END  # Out of retries, kill the flow
        
    # 2. If execution was successful (no error), ALWAYS route to summary.
    return 'summary_agent'


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
workflow.add_node("retry_node", retry_node)  # Reuse SQL generation node for retries


# Design the graph flow
workflow.set_entry_point('router')
workflow.add_conditional_edges(
    'router',
    master_router,
    {
        'chat': 'chat_node',
        'analytics': 'retriever'
    }

)
workflow.add_edge('chat_node', END)  # End after chat response
workflow.add_edge('retriever', 'sql_generation')
workflow.add_edge('sql_generation', 'sql_validation')
workflow.add_conditional_edges(
    'sql_validation',
    post_validation_router,
    {
        'sql_execution': 'sql_execution',
        'retry_node': 'retry_node',
        END: END
    }
)

workflow.add_conditional_edges(
    'sql_execution',
    post_execution_router,
    {
        'retry_node': 'retry_node',
        'summary_agent': 'summary_agent',
        END: END
    }
)
workflow.add_edge('retry_node', 'sql_validation')  # After retrying, go back to validation
workflow.add_edge('summary_agent', END)  # End after summarization

memory = MemorySaver()

app = workflow.compile(checkpointer=memory)