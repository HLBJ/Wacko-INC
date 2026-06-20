from agents.registry import get_agent
from database.db import SessionLocal
from database.models import Task
from services.task_service import TaskService


def run_task(task_id):
    db = SessionLocal()
    try:
        task = db.query(Task).filter(Task.id == task_id).first()
        if task is None:
            return None

        TaskService.update_status(task.id, "IN_PROGRESS")
        agent = get_agent(task.assigned_agent)
        prompt = build_agent_prompt(task, agent)
        run = TaskService.create_run(task.id, task.assigned_agent, prompt)

        try:
            output = agent["handler"](prompt)
            completed = TaskService.complete_run(run.id, output, "COMPLETED")
            TaskService.update_status(task.id, "AWAITING_APPROVAL" if task.requires_approval else "DONE")

            if task.requires_approval:
                TaskService.create_approval(
                    task.id,
                    f"Approve output from {agent['name']}",
                    "Review the generated output before it is used for code, deployment, or external communication."
                )

            return completed
        except Exception as exc:
            TaskService.complete_run(run.id, str(exc), "FAILED")
            TaskService.update_status(task.id, "FAILED")
            raise
    finally:
        db.close()


def build_agent_prompt(task, agent):
    capabilities = ", ".join(agent["capabilities"])
    return f"""
You are the {agent["name"]} in Wacko Inc, a local AI software company.

Role:
{agent["description"]}

Capabilities:
{capabilities}

Task:
{task.title}

Details:
{task.description}

Rules:
- Produce practical, executable work.
- Mention assumptions clearly.
- Mark any action that needs CEO approval.
- Do not claim to have deployed, emailed, purchased, deleted, or published anything.
"""
