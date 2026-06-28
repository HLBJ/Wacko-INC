from services.ai_gateway import generate_file_change_response

def developer_agent(task: str) -> str:
    lowered = task.lower()
    if "frontend agent" in lowered:
        role = "frontend"
    elif "database agent" in lowered:
        role = "database"
    elif "backend agent" in lowered:
        role = "backend"
    else:
        role = "developer"
    return generate_file_change_response(role, task)
