from llm import model_for, run_model

def developer_agent(task: str) -> str:
    prompt = f"""
You are a senior .NET/Python software engineer.

You must implement the following task:

{task}

Rules:
- Write production-ready code
- Include file structure
- Include explanation
"""

    return run_model(model_for("developer", "qwen2.5-coder:3b"), prompt)
