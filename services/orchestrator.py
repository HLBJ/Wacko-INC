import logging

from agents.registry import get_agent
from database.db import SessionLocal
from database.models import Task
from services.architecture_contract import read_contract_text
from services.file_writer import resolve_output_dir, write_agent_output
from services.git_service import commit_if_changed, create_task_branch
from services.project_memory import append_handoff, read_project_memory, read_recent_handoffs, update_project_memory
from services.project_reader import format_project_context, read_relevant_project_context
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
        stored_project_path = task.project.project_path if task.project else ""
        project_description = task.project.description if task.project else ""
        project_id_val = task.project_id

    finally:
        db.close()

    TaskService.update_status(task_id_val, "IN_PROGRESS")
    agent = get_agent(task_assigned_agent)
    project_dir = output_dir or stored_project_path or str(resolve_output_dir(project_name))
    project_context = ""
    try:
        context = read_relevant_project_context(project_dir, f"{task_title}\n{task_description}")
        project_context = format_project_context(context)
    except Exception as context_exc:
        project_context = f"Project context unavailable for {project_dir}: {context_exc}"
    project_memory = read_project_memory(project_dir, project_name)
    recent_handoffs = read_recent_handoffs(project_dir)
    architecture_contract = read_contract_text(project_dir, project_name)
    prompt = build_agent_prompt(
        task_title,
        task_description,
        agent,
        project_dir,
        project_context,
        project_memory,
        recent_handoffs,
        architecture_contract,
    )
    branch_name = ""
    if project_dir:
        branch_result = create_task_branch(project_id_val, task_id_val, task_assigned_agent, project_dir)
        if branch_result and branch_result.get("created"):
            branch_name = branch_result["branch_name"]
            TaskService.update_branch(task_id_val, branch_name)

    run = TaskService.create_run(task_id_val, task_assigned_agent, prompt, branch_name=branch_name)

    try:
        output = agent["handler"](prompt)

        # Write the full agent note and any project files emitted in file blocks.
        try:
            file_result = write_agent_output(
                project_name=project_name,
                task_title=task_title,
                agent_name=agent["name"],
                output=output,
                output_dir=project_dir,
            )
            logger.info("Agent output written to %s", file_result["note_file"])
        except Exception as write_exc:
            # File writing failure must never kill the run
            logger.warning("Could not write agent output to disk: %s", write_exc)
            file_result = {
                "project_dir": None,
                "note_file": None,
                "generated_files": [],
            }

        output_files = [
            path for path in [file_result["note_file"], *file_result["generated_files"]]
            if path
        ]
        memory_file = update_project_memory(
            project_dir,
            project_name,
            task_title,
            agent["name"],
            output,
            file_result["generated_files"],
        )
        append_handoff(
            project_dir,
            task_title,
            agent["name"],
            output,
            file_result["generated_files"],
        )
        output_files.append(str(memory_file))
        completed = TaskService.complete_run(
            run.id,
            output,
            "COMPLETED",
            output_file=file_result["note_file"],
            output_files=output_files,
        )
        commit_result = None
        if project_dir and branch_name:
            commit_result = commit_if_changed(
                project_id_val,
                f"Task {task_id_val}: {task_title}",
                project_dir,
            )
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
            "branch_name": branch_name,
            "commit": commit_result,
            "project_dir": file_result["project_dir"],
            "output_file": file_result["note_file"],
            "output_files": output_files,
        }

    except Exception as exc:
        TaskService.complete_run(run.id, str(exc), "FAILED")
        TaskService.update_status(task_id_val, "FAILED")
        raise


def build_agent_prompt(
    task_title: str,
    task_description: str,
    agent: dict,
    project_dir: str,
    project_context: str,
    project_memory: str,
    recent_handoffs: str,
    architecture_contract: str,
) -> str:
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

Project directory:
{project_dir}

Current project snapshot:
{project_context}

Shared project memory:
{project_memory}

Architecture contract:
{architecture_contract}

Recent handoffs from other agents:
{recent_handoffs}

Rules:
- Produce practical, executable work.
- Act like a careful teammate: read prior decisions, avoid undoing another agent's work, and leave a useful handoff.
- Obey the architecture contract. If the task conflicts with it, explain the conflict in risks instead of silently breaking it.
- When the task requires implementation, create or update real project files.
- Use relative paths only. Never use absolute paths in file blocks.
- Only include files that should be created or changed.
- Mention assumptions clearly.
- Mark any action that needs CEO approval.
- Do not claim to have deployed, emailed, purchased, deleted, or published anything.
"""
