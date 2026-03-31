from agent.graph import app


def run_agent(question):

    

    

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

    result = app.invoke(initial_state)

    return {"result":result.get("result", "No result returned"),
            "generated_sql": result.get("generated_sql", "No SQL generated"),
            "input_tokens": result.get("input_tokens", 0),
            "output_tokens": result.get("output_tokens", 0)}