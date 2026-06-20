from pathlib import Path

from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

import database.models  # noqa
from agents.registry import AGENT_PROFILES
from api.schemas import ApprovalDecision, CompanyGoalCreate, ProjectCreate, TaskCreate
from database.db import Base, engine
from llm import ollama_health
from services.company_service import run_project_tasks, submit_company_goal
from services.orchestrator import run_task
from services.project_service import ProjectService
from services.task_service import TaskService


APP_DIR = Path(__file__).resolve().parent
STATIC_DIR = APP_DIR / "static"

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Wacko Inc OS", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/")
def dashboard():
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/health")
def health():
    return {"status": "ok", "product": "Wacko Inc OS"}


@app.get("/api/ollama/health")
def check_ollama():
    return ollama_health()


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


@app.post("/api/projects")
def create_project(payload: ProjectCreate):
    return ProjectService.create_project(payload.name, payload.description)


@app.get("/api/projects")
def list_projects():
    return ProjectService.list_projects()


@app.post("/api/goals")
def submit_goal(payload: CompanyGoalCreate, background_tasks: BackgroundTasks):
    result = submit_company_goal(payload.goal, auto_start=True)
    if payload.auto_start:
        background_tasks.add_task(
            run_project_tasks,
            result["project"].id,
            {result["planning_task"].id}
        )
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
        requires_approval=payload.requires_approval
    )


@app.get("/api/tasks")
def list_tasks(project_id: int | None = None):
    return TaskService.list_tasks(project_id)


@app.post("/api/tasks/{task_id}/run")
def run_agent_task(task_id: int):
    run = run_task(task_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return run


@app.post("/api/projects/{project_id}/run")
def run_project(project_id: int, background_tasks: BackgroundTasks):
    project = ProjectService.get_project(project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    background_tasks.add_task(run_project_tasks, project_id)
    return {"status": "started", "project_id": project_id}


@app.get("/api/runs")
def list_runs(task_id: int | None = None):
    return TaskService.list_runs(task_id)


@app.get("/api/approvals")
def list_approvals():
    return TaskService.list_approvals()


@app.post("/api/approvals/{approval_id}/decision")
def decide_approval(approval_id: int, payload: ApprovalDecision):
    status = payload.status.upper()
    if status not in {"APPROVED", "REJECTED"}:
        raise HTTPException(status_code=400, detail="Decision must be APPROVED or REJECTED")

    approval = TaskService.decide_approval(approval_id, status, payload.notes or "")
    if approval is None:
        raise HTTPException(status_code=404, detail="Approval not found")

    TaskService.update_status(approval.task_id, "DONE" if status == "APPROVED" else "NEEDS_CHANGES")
    return approval
