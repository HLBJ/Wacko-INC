from llm import model_for, run_model

def reviewer_agent(code: str) -> str:
    prompt = f"""
You are a senior code reviewer and security engineer.

Review the following output:

{code}

Check:
- correctness
- security issues
- missing parts
- improvements

Return:
- APPROVED or REJECTED
- Reason
- Fix suggestions
"""

    return run_model(model_for("reviewer", "qwen2.5:3b"), prompt)
