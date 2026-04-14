from agent.graph import app


async def run_agent(question: str, thread_id: str) -> dict:
    """
    This function serves as the main entry point to run the agent workflow.
    """

    # Initialize the state with the question and any other necessary information
    initial_state = {
        "question": question,
        "generated_sql": None,
        "validated_sql": None,
        "result": None,
        "error": None,
        "retries": 0,
        "input_tokens": 0,
        "output_tokens": 0
    }

    # We pass the thread_id in the config so that it can be used for logging and tracing throughout the workflow
    config = {"configurable": {
        "thread_id": thread_id
    }}
    result = await app.ainvoke(initial_state, config=config)

    return {"result":result.get("result", "No result returned"),
            "generated_sql": result.get("generated_sql", "No SQL generated"),
            "input_tokens": result.get("input_tokens", 0),
            "output_tokens": result.get("output_tokens", 0),
            "result_summary": result.get("result_summary", "No summary generated"),
            "viz_config": result.get("viz_config",{})
            }