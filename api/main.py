from pathlib import Path
import subprocess
import sys

from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from agents.registry import AGENT_PROFILES
from api.schemas import ApprovalDecision, BranchActionCreate, BuildRunCreate, CompanyGoalCreate, GitActionCreate, ProjectCreate, ProjectUpdateCreate, ProjectWorkflowCreate, SettingsUpdate, SupportTicketCreate, SupportTicketUpdate, TaskCreate
from database.db import SessionLocal
from database.models import AgentRun, Approval, BuildRun, Execution, Job, JobEvent, Project, Setting, SupportTicket, Task
from database.schema import ensure_schema
from llm import model_preflight, ollama_health
from services.build_service import list_build_runs, run_project_build
from services.company_service import run_project_tasks, submit_company_goal, submit_project_update
from services.git_service import commit_if_changed as git_commit_if_changed
from services.git_service import commit as git_commit
from services.git_service import delete_branch as git_delete_branch
from services.git_service import init_repo as git_init_repo
from services.git_service import merge_branch as git_merge_branch
from services.git_service import revert_uncommitted as git_revert_uncommitted
from services.git_service import status as git_status
from services.ai_gateway import gateway_health
from services.approval_service import approval_review_package
from services.architecture_contract import ensure_project_contract
from services.job_service import cancel_job, create_job, get_job, job_payload, list_jobs, set_process_id
from services.job_event_service import list_job_events
from services.orchestrator import run_task
from services.project_file_service import list_project_files, read_project_file
from services.project_overview import project_overview
from services.project_quality import audit_python_project
from services.project_report import build_ceo_report, save_ceo_report
from services.project_security import scan_project_security
from services.project_service import ProjectService
from services.project_templates import list_templates
from services.settings_service import get_settings, update_settings
from services.support_service import create_ticket, escalate_ticket, list_tickets, triage_ticket, update_ticket
from services.task_service import TaskService


APP_DIR = Path(__file__).resolve().parent
STATIC_DIR = APP_DIR / "static"

ensure_schema()

app = FastAPI(title="Wacko Inc OS", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


def start_worker(job_id: int):
    process = subprocess.Popen(
        [sys.executable, "-m", "services.job_worker", str(job_id)],
        cwd=str(Path.cwd()),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
    )
    set_process_id(job_id, process.pid)
    return process.pid


@app.get("/")
def dashboard():
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/health")
def health():
    return {"status": "ok", "product": "Wacko Inc OS"}


@app.get("/api/ollama/health")
def check_ollama():
    return ollama_health()


@app.get("/api/ollama/preflight")
def check_ollama_preflight():
    return model_preflight()


@app.get("/api/ai-gateway/health")
def check_ai_gateway():
    return gateway_health()


@app.get("/api/settings")
def settings():
    return get_settings()


@app.put("/api/settings")
def update_app_settings(payload: SettingsUpdate):
    if hasattr(payload, "model_dump"):
        data = payload.model_dump(exclude_unset=True)
    else:
        data = payload.dict(exclude_unset=True)
    return update_settings(data)


@app.post("/api/admin/clear-database")
def clear_database():
    db = SessionLocal()
    try:
        for model in (Approval, AgentRun, BuildRun, JobEvent, Job, SupportTicket, Task, Project, Execution, Setting):
            db.query(model).delete()
        db.commit()
        return {"status": "cleared"}
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


@app.get("/api/agents")
def list_agents():
    return {
        key: {
            "name": value["name"],
            "description": value["description"],
            "capabilities": value["capabilities"],
        }
        for key, value in AGENT_PROFILES.items()
    }


@app.get("/api/templates")
def templates():
    return list_templates()


@app.post("/api/support-tickets")
def create_support_ticket(payload: SupportTicketCreate):
    return create_ticket(payload.project_id, payload.sender_email, payload.subject, payload.body)


@app.get("/api/support-tickets")
def support_tickets(project_id: int | None = None, status: str | None = None):
    return list_tickets(project_id=project_id, status=status)


@app.post("/api/support-tickets/{ticket_id}/triage")
def triage_support_ticket(ticket_id: int):
    result = triage_ticket(ticket_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Support ticket not found")
    return result


@app.patch("/api/support-tickets/{ticket_id}")
def update_support_ticket(ticket_id: int, payload: SupportTicketUpdate):
    result = update_ticket(ticket_id, payload.status, payload.suggested_reply)
    if result is None:
        raise HTTPException(status_code=404, detail="Support ticket not found")
    return result


@app.post("/api/support-tickets/{ticket_id}/escalate")
def escalate_support_ticket(ticket_id: int):
    result = escalate_ticket(ticket_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Support ticket not found")
    if result.get("error"):
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@app.post("/api/projects")
def create_project(payload: ProjectCreate):
    return ProjectService.create_project(payload.name, payload.description, payload.project_path or "")


@app.get("/api/projects")
def list_projects():
    return ProjectService.list_projects()


@app.get("/api/projects/{project_id}/overview")
def get_project_overview(project_id: int):
    result = project_overview(project_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return result


@app.get("/api/projects/{project_id}/ceo-report")
def get_project_ceo_report(project_id: int):
    result = build_ceo_report(project_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return result


@app.post("/api/projects/{project_id}/ceo-report/save")
def save_project_ceo_report(project_id: int):
    result = save_ceo_report(project_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return result


@app.get("/api/projects/{project_id}/files")
def project_files(project_id: int, include_notes: bool = True):
    result = list_project_files(project_id, include_notes)
    if result is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return result


@app.get("/api/projects/{project_id}/files/content")
def project_file_content(project_id: int, path: str):
    try:
        result = read_project_file(project_id, path)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="File not found")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if result is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return result


@app.get("/api/projects/{project_id}/quality")
def project_quality(project_id: int):
    result = audit_python_project(project_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return result


@app.get("/api/projects/{project_id}/security")
def project_security(project_id: int):
    result = scan_project_security(project_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return result


@app.post("/api/projects/{project_id}/architecture")
def project_architecture(project_id: int, overwrite: bool = False):
    result = ensure_project_contract(project_id, overwrite=overwrite)
    if result is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return result


@app.post("/api/projects/{project_id}/workflow")
def project_workflow(project_id: int, payload: ProjectWorkflowCreate, background_tasks: BackgroundTasks):
    project = ProjectService.get_project(project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")

    workflow = payload.workflow.strip().lower()
    app_settings = get_settings()
    max_fix_attempts = payload.max_fix_attempts or app_settings["max_fix_attempts"]
    max_cycles = payload.max_cycles or app_settings["max_autopilot_cycles"]
    if workflow == "auto_next":
        overview = project_overview(project_id)
        if not overview:
            raise HTTPException(status_code=404, detail="Project not found")
        recommendation = overview.get("recommended_next_action") or {}
        if not recommendation.get("can_run", False):
            return {
                "status": "waiting",
                "workflow": workflow,
                "recommended": recommendation,
                "project_id": project_id,
            }
        workflow = recommendation.get("workflow", "release_check")

    if workflow == "run_agents":
        preflight = model_preflight(["developer", "security", "testing"])
        if not preflight["ok"]:
            raise HTTPException(status_code=503, detail=preflight)
        job = create_job("agent_project_run", "Run project agents", project_id)
        start_worker(job.id)
        return {"status": "started", "workflow": workflow, "requested_workflow": payload.workflow, "project_id": project_id, "job_id": job.id}

    if workflow == "full_cycle":
        preflight = model_preflight(["developer", "security", "testing"])
        if not preflight["ok"]:
            raise HTTPException(status_code=503, detail=preflight)
        job = create_job(
            "full_cycle",
            "Full agent build cycle",
            project_id,
            payload={
                "output_dir": project.project_path,
                "project_path": project.project_path,
                "auto_fix": True,
                "max_fix_attempts": max_fix_attempts,
            },
        )
        start_worker(job.id)
        return {"status": "started", "workflow": workflow, "requested_workflow": payload.workflow, "project_id": project_id, "job_id": job.id}

    if workflow == "autopilot":
        job = create_job(
            "autopilot",
            "Project autopilot",
            project_id,
            payload={
                "output_dir": project.project_path,
                "project_path": project.project_path,
                "auto_fix": True,
                "max_fix_attempts": max_fix_attempts,
                "max_cycles": max_cycles,
            },
        )
        start_worker(job.id)
        return {"status": "started", "workflow": workflow, "requested_workflow": payload.workflow, "project_id": project_id, "job_id": job.id}

    if workflow in {"build_until_pass", "fix_project"}:
        preflight = model_preflight(["developer", "security", "testing"])
        if not preflight["ok"]:
            raise HTTPException(status_code=503, detail=preflight)
        job = create_job(
            "build",
            "Build until pass",
            project_id,
            payload={
                "project_path": project.project_path,
                "auto_fix": True,
                "max_fix_attempts": max_fix_attempts,
            },
        )
        start_worker(job.id)
        return {"status": "started", "workflow": workflow, "requested_workflow": payload.workflow, "project_id": project_id, "job_id": job.id}

    if workflow == "refresh_architecture":
        result = ensure_project_contract(project_id, overwrite=payload.overwrite_architecture)
        return {"status": "completed", "workflow": workflow, "requested_workflow": payload.workflow, "result": result}

    if workflow == "health_check":
        return {
            "status": "completed",
            "workflow": workflow,
            "requested_workflow": payload.workflow,
            "quality": audit_python_project(project_id),
            "security": scan_project_security(project_id),
        }

    if workflow == "release_check":
        overview = project_overview(project_id)
        blockers = []
        if not overview:
            raise HTTPException(status_code=404, detail="Project not found")
        if not overview.get("project_exists"):
            blockers.append("Project path does not exist.")
        if not overview.get("architecture_ready"):
            blockers.append("Architecture contract is missing.")
        if (overview.get("latest_build") or {}).get("status") != "PASSED":
            blockers.append("Latest build/test run has not passed.")
        if overview.get("quality", {}).get("status") != "PASS":
            blockers.append("Quality review is not passing.")
        blocking_security = [
            item for item in overview.get("security", {}).get("findings", [])
            if item.get("severity") in {"CRITICAL", "HIGH"}
        ]
        if blocking_security:
            blockers.append(f"{len(blocking_security)} high-risk security finding(s) remain.")
        if overview.get("pending_approvals", 0):
            blockers.append(f"{overview['pending_approvals']} approval(s) are still pending.")
        unfinished = {
            status: count for status, count in overview.get("task_counts", {}).items()
            if status not in {"DONE", "AWAITING_APPROVAL"} and count
        }
        if unfinished:
            blockers.append("Unfinished tasks remain: " + ", ".join(f"{key}={value}" for key, value in unfinished.items()))
        return {
            "status": "completed",
            "workflow": workflow,
            "requested_workflow": payload.workflow,
            "ready": not blockers,
            "blockers": blockers,
            "overview": overview,
        }

    raise HTTPException(status_code=400, detail=f"Unknown workflow: {payload.workflow}")


@app.post("/api/goals")
def submit_goal(payload: CompanyGoalCreate, background_tasks: BackgroundTasks):
    preflight = model_preflight(["manager"])
    if not preflight["ok"]:
        raise HTTPException(status_code=503, detail=preflight)
    result = submit_company_goal(
        payload.goal,
        auto_start=False,
        output_dir=payload.output_dir,
        stack=payload.stack,
    )
    if payload.auto_start:
        job = create_job(
            "agent_project_run",
            "Run project agents",
            result["project"].id,
            input_text=payload.goal,
            payload={
                "skip_task_ids": [result["planning_task"].id],
                "output_dir": payload.output_dir,
            },
        )
        start_worker(job.id)
        result["auto_started"] = True
    return result


@app.post("/api/project-updates")
def submit_update(payload: ProjectUpdateCreate, background_tasks: BackgroundTasks):
    preflight = model_preflight(["manager"])
    if not preflight["ok"]:
        raise HTTPException(status_code=503, detail=preflight)
    result = submit_project_update(
        payload.project_path,
        payload.instructions,
        auto_start=False,
    )
    if payload.auto_start:
        job = create_job(
            "agent_project_update",
            "Run project update agents",
            result["project"].id,
            input_text=payload.instructions,
            payload={
                "skip_task_ids": [result["planning_task"].id],
                "output_dir": result["project_path"],
            },
        )
        start_worker(job.id)
        result["auto_started"] = True
    return result


@app.post("/api/tasks")
def create_task(payload: TaskCreate):
    return TaskService.create_task(
        project_id=payload.project_id,
        title=payload.title,
        description=payload.description,
        assigned_agent=payload.assigned_agent,
        priority=payload.priority,
        requires_approval=payload.requires_approval,
    )


@app.get("/api/tasks")
def list_tasks(project_id: int | None = None):
    return TaskService.list_tasks(project_id)


@app.post("/api/tasks/{task_id}/run")
def run_agent_task(task_id: int):
    preflight = model_preflight(["developer", "security", "testing"])
    if not preflight["ok"]:
        raise HTTPException(status_code=503, detail=preflight)
    job = create_job("agent_task_run", "Run single agent task", task_id=task_id)
    start_worker(job.id)
    return {"status": "started", "job_id": job.id, "task_id": task_id}


@app.post("/api/projects/{project_id}/run")
def run_project(project_id: int, background_tasks: BackgroundTasks):
    project = ProjectService.get_project(project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    preflight = model_preflight(["developer", "security", "testing"])
    if not preflight["ok"]:
        raise HTTPException(status_code=503, detail=preflight)
    job = create_job("agent_project_run", "Run project agents", project_id)
    start_worker(job.id)
    return {"status": "started", "project_id": project_id, "job_id": job.id}


@app.post("/api/projects/{project_id}/build")
def build_project(project_id: int, payload: BuildRunCreate, background_tasks: BackgroundTasks):
    project = ProjectService.get_project(project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    if payload.auto_fix:
        preflight = model_preflight(["developer", "security", "testing"])
        if not preflight["ok"]:
            raise HTTPException(status_code=503, detail=preflight)
    job = create_job(
        "build",
        "Run build/test",
        project_id,
        input_text=str(payload),
        payload={
            "project_path": payload.project_path,
            "stack": payload.stack,
            "auto_fix": payload.auto_fix,
            "max_fix_attempts": payload.max_fix_attempts,
        },
    )
    start_worker(job.id)
    return {"status": "started", "project_id": project_id, "job_id": job.id}


@app.get("/api/build-runs")
def build_runs(project_id: int | None = None):
    return list_build_runs(project_id)


@app.get("/api/jobs")
def jobs(project_id: int | None = None):
    return list_jobs(project_id)


@app.get("/api/job-events")
def job_events(project_id: int | None = None, job_id: int | None = None, limit: int = 200):
    return list_job_events(project_id=project_id, job_id=job_id, limit=limit)


@app.post("/api/jobs/{job_id}/cancel")
def cancel_job_endpoint(job_id: int):
    result = cancel_job(job_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return result


@app.post("/api/jobs/{job_id}/retry")
def retry_job_endpoint(job_id: int, background_tasks: BackgroundTasks):
    original = get_job(job_id)
    if original is None:
        raise HTTPException(status_code=404, detail="Job not found")

    if original.job_type in {"agent_project_run", "agent_project_update", "full_cycle", "autopilot"}:
        preflight = model_preflight(["developer", "security", "testing"])
        if not preflight["ok"]:
            raise HTTPException(status_code=503, detail=preflight)
        new_job = create_job(
            original.job_type,
            f"Retry: {original.title}",
            original.project_id,
            input_text=original.input_text,
            retry_of_job_id=original.id,
            payload=job_payload(original),
        )
        start_worker(new_job.id)
        return new_job

    if original.job_type == "agent_task_run" and original.task_id:
        preflight = model_preflight(["developer", "security", "testing"])
        if not preflight["ok"]:
            raise HTTPException(status_code=503, detail=preflight)
        new_job = create_job(
            original.job_type,
            f"Retry: {original.title}",
            original.project_id,
            original.task_id,
            original.input_text,
            retry_of_job_id=original.id,
            payload=job_payload(original),
        )
        start_worker(new_job.id)
        return new_job

    if original.job_type == "build":
        payload = job_payload(original)
        if payload.get("auto_fix", True):
            preflight = model_preflight(["developer", "security", "testing"])
            if not preflight["ok"]:
                raise HTTPException(status_code=503, detail=preflight)
        new_job = create_job(
            original.job_type,
            f"Retry: {original.title}",
            original.project_id,
            input_text=original.input_text,
            retry_of_job_id=original.id,
            payload=payload,
        )
        start_worker(new_job.id)
        return new_job

    raise HTTPException(status_code=400, detail=f"Job type cannot be retried: {original.job_type}")


@app.post("/api/projects/{project_id}/git/init")
def init_project_git(project_id: int, payload: GitActionCreate):
    result = git_init_repo(project_id, payload.project_path)
    if result is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return result


@app.post("/api/projects/{project_id}/git/status")
def project_git_status(project_id: int, payload: GitActionCreate):
    result = git_status(project_id, payload.project_path)
    if result is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return result


@app.post("/api/projects/{project_id}/git/commit")
def commit_project_git(project_id: int, payload: GitActionCreate):
    result = git_commit(project_id, payload.message or "Wacko Inc agent changes", payload.project_path)
    if result is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return result


@app.post("/api/projects/{project_id}/git/approve")
def approve_project_changes(project_id: int, payload: GitActionCreate):
    result = git_commit_if_changed(project_id, payload.message or "Approve Wacko Inc changes", payload.project_path)
    if result is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return result


@app.post("/api/projects/{project_id}/git/revert")
def revert_project_changes(project_id: int, payload: GitActionCreate):
    result = git_revert_uncommitted(project_id, payload.project_path)
    if result is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return result


@app.post("/api/projects/{project_id}/git/merge-branch")
def merge_project_branch(project_id: int, payload: BranchActionCreate):
    result = git_merge_branch(project_id, payload.branch_name, payload.project_path)
    if result is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return result


@app.post("/api/projects/{project_id}/git/delete-branch")
def delete_project_branch(project_id: int, payload: BranchActionCreate):
    result = git_delete_branch(project_id, payload.branch_name, payload.project_path)
    if result is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return result


@app.get("/api/runs")
def list_runs(task_id: int | None = None):
    return TaskService.list_runs(task_id)


@app.get("/api/approvals")
def list_approvals():
    return TaskService.list_approvals()


@app.get("/api/approvals/{approval_id}/review")
def approval_review(approval_id: int):
    result = approval_review_package(approval_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Approval not found")
    return result


@app.post("/api/approvals/{approval_id}/decision")
def decide_approval(approval_id: int, payload: ApprovalDecision):
    status = payload.status.upper()
    if status not in {"APPROVED", "REJECTED"}:
        raise HTTPException(status_code=400, detail="Decision must be APPROVED or REJECTED")

    if status == "APPROVED":
        review = approval_review_package(approval_id)
        quality_status = review.get("quality", {}).get("status") if review else None
        security_findings = review.get("security", {}).get("findings", []) if review else []
        blocking_security = any(item.get("severity") in {"CRITICAL", "HIGH"} for item in security_findings)
        build_status = review.get("latest_build").status if review and review.get("latest_build") else None
        notes = (payload.notes or "").lower()
        if (quality_status == "FAIL" or build_status == "FAILED" or blocking_security) and "override" not in notes:
            raise HTTPException(
                status_code=400,
                detail="Build, quality, or security is failing. Add 'override' in approval notes to approve anyway.",
            )

    approval = TaskService.decide_approval(approval_id, status, payload.notes or "")
    if approval is None:
        raise HTTPException(status_code=404, detail="Approval not found")

    TaskService.update_status(approval.task_id, "DONE" if status == "APPROVED" else "NEEDS_CHANGES")
    return approval
