from llm import model_for, run_model

def manager_agent(user_request: str) -> str:
    prompt = f"""
You are a senior software project manager.

Task:
Break the following request into a structured software plan.

User Request:
{user_request}

Output format:
- Summary
- Requirements
- Task List (numbered)
- Risks
- File-producing tasks should tell specialist agents which files they must create
"""

    return run_model(model_for("manager", "qwen2.5:3b"), prompt)
