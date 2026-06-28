import json

from database.db import SessionLocal
from database.models import AgentRun, Approval, BuildRun, Task
from services.git_service import status as git_status
from services.project_quality import audit_python_project
from services.project_security import scan_project_security


def _parse_output_files(value: str | None) -> list[str]:
    if not value:
        return []
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return [value]
    return parsed if isinstance(parsed, list) else []


def approval_review_package(approval_id: int) -> dict | None:
    db = SessionLocal()
    try:
        approval = db.query(Approval).filter(Approval.id == approval_id).first()
        if approval is None:
            return None

        task = db.query(Task).filter(Task.id == approval.task_id).first()
        latest_run = (
            db.query(AgentRun)
            .filter(AgentRun.task_id == approval.task_id)
            .order_by(AgentRun.created_at.desc())
            .first()
        )
        latest_build = None
        if task is not None:
            latest_build = (
                db.query(BuildRun)
                .filter(BuildRun.project_id == task.project_id)
                .order_by(BuildRun.created_at.desc())
                .first()
            )

        project_id = task.project_id if task else None
        project_path = task.project.project_path if task and task.project else ""
        branch_name = task.branch_name if task else ""
        git = git_status(project_id, project_path) if project_id else None
        quality = audit_python_project(project_id) if project_id else None
        security = scan_project_security(project_id) if project_id else None

        return {
            "approval": approval,
            "task": task,
            "latest_run": latest_run,
            "output_files": _parse_output_files(latest_run.output_files if latest_run else ""),
            "latest_build": latest_build,
            "git": git,
            "quality": quality,
            "security": security,
            "project_id": project_id,
            "project_path": project_path,
            "branch_name": branch_name,
        }
    finally:
        db.close()
