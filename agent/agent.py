import json
from agent.graph import app
from langchain_core.messages import HumanMessage


async def run_agent(question: str, thread_id: str, org_id: str, user_id: str) :
    """
    This function serves as the main entry point to run the agent workflow.
    """

    # Initialize the state with the question and any other necessary information
    initial_state = {
        "question": question,
        "messages": [HumanMessage(content=question)],
        "generated_sql": None,
        "validated_sql": None,
        "result": None,
        "error": None,
        "retries": 0,
        "input_tokens": 0,
        "output_tokens": 0,
        'org_id': org_id,
        'user_id': user_id
    }

    # We pass the thread_id in the config so that it can be used for logging and tracing throughout the workflow
    config = {
        "configurable":{
            "thread_id": thread_id
        },
        "tags": [ org_id ],
        "metdata":{
            "org_id": org_id,
            "user_id": user_id,
            "session_id": thread_id
        }
    }

    # Stream the execution of the agent workflow and get the final result
    async for event in app.astream(initial_state, config=config):
        for node_name, state_update in event.items():
            if node_name == "router":
                if state_update.get("router_decision") == "analytics":
                    yield json.dumps({"status": "Gathering relevant database schemas..."}) + "\n"
                else:
                    yield json.dumps({"status": "Formulating response..."}) + "\n"
            elif node_name == "retriever":
                yield json.dumps({"status": "Generating SQL, might take a moment..."}) + "\n"
            elif node_name == "sql_generation":
                yield json.dumps({"status": "Validating SQL query..."}) + "\n"
            elif node_name == "sql_validation":
                if state_update.get("error"):
                    yield json.dumps({"status": "Syntax error detected, regenerating SQL..."}) + "\n"
                else:
                    yield json.dumps({"status": "Executing SQL query against database..."}) + "\n"
            elif node_name == "sql_execution":
                if state_update.get("error"):
                    yield json.dumps({"status": "Error executing SQL, applying corrections..."}) + "\n"
                else:
                    yield json.dumps({"status": "Analyzing results and generating final insights..."}) + "\n"
            elif node_name == "retry_node":
                yield json.dumps({"status": "Re-validating corrected SQL..."}) + "\n"
            elif node_name == "summary_agent":
                yield json.dumps({"status": "Generating final insights..."}) + "\n"
            elif node_name == "chat_node":
                yield json.dumps({"status": "Formatting final payload..."}) + "\n"
    final_state = app.get_state(config).values
    final_result = {
        "generated_sql": final_state.get("generated_sql"),
        "result": final_state.get("result"),
        "result_summary": final_state.get("result_summary")
    }
    yield json.dumps(final_result) + "\n"
            

    