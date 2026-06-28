from pathlib import Path

from agents.registry import AGENT_PROFILES
from database.db import SessionLocal
from database.models import AgentRun, Approval, BuildRun, Job, Project, SupportTicket, Task
from services.architecture_contract import detect_stack_from_path
from services.file_writer import resolve_output_dir
from services.project_quality import audit_python_project
from services.project_security import scan_project_security


def _project_path(project: Project) -> str:
    return str(Path(project.project_path or resolve_output_dir(project.name)).resolve())


def _build_summary(build: BuildRun | None) -> dict | None:
    if build is None:
        return None
    return {
        "id": build.id,
        "status": build.status,
        "stack": build.stack,
        "project_path": build.project_path,
        "branch_name": build.branch_name,
        "command": build.command,
        "exit_code": build.exit_code,
        "created_at": build.created_at,
        "completed_at": build.completed_at,
    }


def _job_summary(job: Job | None) -> dict | None:
    if job is None:
        return None
    return {
        "id": job.id,
        "job_type": job.job_type,
        "status": job.status,
        "title": job.title,
        "process_id": job.process_id,
        "created_at": job.created_at,
        "started_at": job.started_at,
        "completed_at": job.completed_at,
    }


def recommended_next_action(overview: dict) -> dict:
    latest_job = overview.get("latest_job") or {}
    task_counts = overview.get("task_counts") or {}
    latest_build = overview.get("latest_build") or {}
    quality = overview.get("quality") or {}
    security = overview.get("security") or {}

    if latest_job.get("status") in {"PENDING", "RUNNING"}:
        return {
            "workflow": "wait",
            "label": "Wait for current job",
            "reason": f"{latest_job.get('title') or 'A job'} is still {latest_job.get('status')}.",
            "can_run": False,
        }

    if not overview.get("project_exists"):
        return {
            "workflow": "run_agents",
            "label": "Create project files",
            "reason": "The project folder does not exist yet, so agents should create the initial files.",
            "can_run": True,
        }

    if not overview.get("architecture_ready"):
        return {
            "workflow": "refresh_architecture",
            "label": "Create architecture contract",
            "reason": "Agents need a shared architecture contract before coordinated edits.",
            "can_run": True,
        }

    unfinished = sum(count for status, count in task_counts.items() if status in {"BACKLOG", "NEEDS_CHANGES", "FAILED"})
    if unfinished:
        return {
            "workflow": "run_agents",
            "label": "Run unfinished agent tasks",
            "reason": f"{unfinished} task(s) still need agent work.",
            "can_run": True,
        }

    if latest_build.get("status") != "PASSED":
        return {
            "workflow": "build_until_pass",
            "label": "Build and repair",
            "reason": "The latest build/test run has not passed.",
            "can_run": True,
        }

    high_security = [
        item for item in security.get("findings", [])
        if item.get("severity") in {"CRITICAL", "HIGH"}
    ]
    if quality.get("status") != "PASS" or high_security:
        return {
            "workflow": "build_until_pass",
            "label": "Repair quality/security findings",
            "reason": "Quality or high-risk security findings remain.",
            "can_run": True,
        }

    if overview.get("pending_approvals"):
        return {
            "workflow": "release_check",
            "label": "Review pending approvals",
            "reason": f"{overview['pending_approvals']} approval(s) need CEO review.",
            "can_run": True,
        }

    return {
        "workflow": "release_check",
        "label": "Run release readiness check",
        "reason": "No obvious blockers remain.",
        "can_run": True,
    }


def _agent_workload(tasks: list[Task], latest_runs: dict[str, AgentRun]) -> list[dict]:
    workload = []
    for key, profile in AGENT_PROFILES.items():
        assigned = [task for task in tasks if task.assigned_agent == key]
        counts: dict[str, int] = {}
        for task in assigned:
            counts[task.status] = counts.get(task.status, 0) + 1

        latest_task = sorted(assigned, key=lambda item: item.updated_at or item.created_at, reverse=True)
        latest_run = latest_runs.get(key)
        workload.append({
            "agent": key,
            "name": profile["name"],
            "description": profile["description"],
            "task_counts": counts,
            "task_total": len(assigned),
            "latest_task": {
                "id": latest_task[0].id,
                "title": latest_task[0].title,
                "status": latest_task[0].status,
                "priority": latest_task[0].priority,
            } if latest_task else None,
            "latest_run": {
                "id": latest_run.id,
                "status": latest_run.status,
                "created_at": latest_run.created_at,
                "completed_at": latest_run.completed_at,
            } if latest_run else None,
        })
    return workload


def project_overview(project_id: int, ignore_job_id: int | None = None) -> dict | None:
    db = SessionLocal()
    try:
        project = db.query(Project).filter(Project.id == project_id).first()
        if project is None:
            return None

        tasks = db.query(Task).filter(Task.project_id == project_id).all()
        task_counts: dict[str, int] = {}
        for task in tasks:
            task_counts[task.status] = task_counts.get(task.status, 0) + 1

        latest_run_rows = (
            db.query(AgentRun)
            .join(Task, AgentRun.task_id == Task.id)
            .filter(Task.project_id == project_id)
            .order_by(AgentRun.created_at.desc())
            .all()
        )
        latest_runs = {}
        for run in latest_run_rows:
            latest_runs.setdefault(run.agent_name, run)

        pending_approvals = (
            db.query(Approval)
            .join(Task, Approval.task_id == Task.id)
            .filter(Task.project_id == project_id, Approval.status == "PENDING")
            .count()
        )
        latest_build = (
            db.query(BuildRun)
            .filter(BuildRun.project_id == project_id)
            .order_by(BuildRun.created_at.desc())
            .first()
        )
        latest_job_query = db.query(Job).filter(Job.project_id == project_id)
        if ignore_job_id is not None:
            latest_job_query = latest_job_query.filter(Job.id != ignore_job_id)
        latest_job = latest_job_query.order_by(Job.created_at.desc()).first()
        support_rows = db.query(SupportTicket.status).filter(SupportTicket.project_id == project_id).all()
        support_counts: dict[str, int] = {}
        for (status,) in support_rows:
            support_counts[status] = support_counts.get(status, 0) + 1

        root = Path(_project_path(project))
        architecture_ready = (root / ".wacko" / "architecture.json").exists() and (root / "ARCHITECTURE.md").exists()
        stack = detect_stack_from_path(str(root)) if root.exists() else "unknown"

        summary = {
            "project": {
                "id": project.id,
                "name": project.name,
                "description": project.description,
                "status": project.status,
                "project_path": str(root),
                "created_at": project.created_at,
                "updated_at": project.updated_at,
            },
            "project_exists": root.exists(),
            "stack": stack,
            "architecture_ready": architecture_ready,
            "task_counts": task_counts,
            "task_total": sum(task_counts.values()),
            "pending_approvals": pending_approvals,
            "latest_build": _build_summary(latest_build),
            "latest_job": _job_summary(latest_job),
            "agent_workload": _agent_workload(tasks, latest_runs),
            "support_counts": support_counts,
            "support_total": sum(support_counts.values()),
        }
    finally:
        db.close()

    try:
        summary["quality"] = audit_python_project(project_id)
    except Exception as exc:
        summary["quality"] = {"status": "ERROR", "findings": [{"severity": "HIGH", "file": "", "message": str(exc)}]}

    try:
        summary["security"] = scan_project_security(project_id)
    except Exception as exc:
        summary["security"] = {"status": "ERROR", "findings": [{"severity": "HIGH", "file": "", "message": str(exc)}]}

    summary["recommended_next_action"] = recommended_next_action(summary)

    return summary
