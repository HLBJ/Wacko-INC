import logging
from pathlib import Path

from agents.registry import get_agent
from database.db import SessionLocal
from database.models import Task
from services.file_writer import write_agent_output
from services.task_service import TaskService

logger = logging.getLogger(__name__)


def run_task(task_id: int, output_dir: str | None = None) -> dict | None:
    """
    Run the agent assigned to a task and return a plain dict result.

    Returns None if the task does not exist.
    Raises on unexpected agent errors (caller decides how to handle).

    The DetachedInstanceError that previously occurred was caused by returning
    a SQLAlchemy ORM object after the session had already been closed in the
    finally block.  We now return a plain dict so there is no live ORM object
    to detach.
    """
    db = SessionLocal()
    try:
        task = db.query(Task).filter(Task.id == task_id).first()
        if task is None:
            return None

        # Snapshot everything we need before the session closes
        task_id_val = task.id
        task_title = task.title
        task_description = task.description
        task_assigned_agent = task.assigned_agent
        task_requires_approval = bool(task.requires_approval)
        project_name = task.project.name if task.project else "Project"

    finally:
        db.close()

    TaskService.update_status(task_id_val, "IN_PROGRESS")
    agent = get_agent(task_assigned_agent)
    prompt = build_agent_prompt(task_title, task_description, agent)
    run = TaskService.create_run(task_id_val, task_assigned_agent, prompt)

    try:
        output = agent["handler"](prompt)

        # --- Write output to disk ---
        try:
            file_path = write_agent_output(
                project_name=project_name,
                task_title=task_title,
                agent_name=agent["name"],
                output=output,
                output_dir=output_dir,
            )
            logger.info("Agent output written to %s", file_path)
        except Exception as write_exc:
            # File writing failure must never kill the run
            logger.warning("Could not write agent output to disk: %s", write_exc)
            file_path = None

        completed = TaskService.complete_run(run.id, output, "COMPLETED")
        TaskService.update_status(
            task_id_val,
            "AWAITING_APPROVAL" if task_requires_approval else "DONE",
        )

        if task_requires_approval:
            TaskService.create_approval(
                task_id_val,
                f"Approve output from {agent['name']}",
                "Review the generated output before it is used for code, deployment, or external communication.",
            )

        # Return a plain dict — no live ORM object, so no DetachedInstanceError
        return {
            "run_id": completed.id if completed else run.id,
            "task_id": task_id_val,
            "task_title": task_title,
            "agent_name": task_assigned_agent,
            "status": "COMPLETED",
            "output_file": str(file_path) if file_path else None,
        }

    except Exception as exc:
        TaskService.complete_run(run.id, str(exc), "FAILED")
        TaskService.update_status(task_id_val, "FAILED")
        raise


def build_agent_prompt(task_title: str, task_description: str, agent: dict) -> str:
    capabilities = ", ".join(agent["capabilities"])
    return f"""
You are the {agent["name"]} in Wacko Inc, a local AI software company.

Role:
{agent["description"]}

Capabilities:
{capabilities}

Task:
{task_title}

Details:
{task_description}

Rules:
- Produce practical, executable work.
- Mention assumptions clearly.
- Mark any action that needs CEO approval.
- Do not claim to have deployed, emailed, purchased, deleted, or published anything.
"""
