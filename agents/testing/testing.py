from services.ai_gateway import generate_file_change_response


def testing_agent(task: str) -> str:
    return generate_file_change_response("testing", task)
