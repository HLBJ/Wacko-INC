import json
from datetime import datetime
from pathlib import Path

from database.db import SessionLocal
from database.models import BuildRun, Project
from services.command_runner import run_command
from services.file_writer import resolve_output_dir
from services.git_service import current_branch_for_path
from services.project_quality import audit_python_project
from services.project_security import scan_project_security
from services.task_service import TaskService


def detect_stack(project_path: str) -> str:
    root = Path(project_path)
    if (root / "backend" / "requirements.txt").exists() and (root / "frontend" / "package.json").exists():
        return "fastapi-vue"
    if (root / "requirements.txt").exists() or (root / "app" / "main.py").exists():
        return "fastapi"
    if (root / "package.json").exists():
        return "vue"
    if any(root.rglob("*.csproj")) or (root / "src" / "Program.cs").exists():
        return "dotnet-api"
    return "unknown"


def build_commands(stack: str, project_path: str) -> list[dict]:
    root = Path(project_path)
    if stack == "fastapi":
        compile_targets = [target for target in ["app", "tests"] if (root / target).exists()]
        if not compile_targets:
            compile_targets = ["."]
        return [
            {"command": ["python", "-m", "compileall", *compile_targets], "cwd": str(root)},
            {"command": ["python", "-c", "import app.main"], "cwd": str(root)},
            {"command": ["python", "-m", "pytest", "-q"], "cwd": str(root)},
        ]
    if stack == "vue":
        return [
            {"command": ["npm", "install"], "cwd": str(root)},
            {"command": ["npm", "run", "build"], "cwd": str(root)},
        ]
    if stack == "fastapi-vue":
        backend = root / "backend"
        compile_targets = [target for target in ["app", "tests"] if (backend / target).exists()]
        if not compile_targets:
            compile_targets = ["."]
        return [
            {"command": ["python", "-m", "compileall", *compile_targets], "cwd": str(backend)},
            {"command": ["python", "-c", "import app.main"], "cwd": str(backend)},
            {"command": ["python", "-m", "pytest", "-q"], "cwd": str(backend)},
            {"command": ["npm", "install"], "cwd": str(root / "frontend")},
            {"command": ["npm", "run", "build"], "cwd": str(root / "frontend")},
        ]
    if stack == "dotnet-api":
        return [
            {"command": ["dotnet", "build"], "cwd": str(root / "src" if (root / "src").exists() else root)},
            {"command": ["dotnet", "test"], "cwd": str(root)},
        ]
    return [{"command": ["python", "-m", "compileall", "."], "cwd": str(root)}]


def choose_fix_agent(
    stack: str,
    failed_result: dict | None,
    quality: dict | None,
    security: dict | None = None,
) -> str:
    output = ""
    command = ""
    if failed_result:
        output = str(failed_result.get("output", "")).lower()
        command = str(failed_result.get("command", "")).lower()

    quality_text = json.dumps((quality or {}).get("findings", [])).lower()
    security_text = json.dumps((security or {}).get("findings", [])).lower()
    combined = f"{command}\n{output}\n{quality_text}\n{security_text}"

    if "wacko security review" in command or any(token in combined for token in ["hardcoded", "secret", "credential", "cors", "private key"]):
        return "security"
    if stack in {"vue"} or "npm" in command or "vite" in combined or "frontend/" in combined or ".vue" in combined:
        return "frontend"
    if any(token in combined for token in ["database.py", "models.py", "migration", "sqlalchemy", "dbcontext", "schema", "jsonb", "get_db"]):
        return "database"
    if "pytest" in command and not any(token in combined for token in ["importerror", "modulenotfounderror", "attributeerror", "app/", "backend/app/"]):
        return "testing"
    if any(token in combined for token in ["test_", "assert ", "fixture"]):
        return "testing"
    return "backend"


def format_fix_summary(
    failed_result: dict | None,
    quality: dict | None,
    security: dict | None = None,
) -> str:
    sections = []
    if failed_result:
        sections.append(
            "Primary failure:\n"
            f"Command: {failed_result.get('command', '')}\n"
            f"Output:\n{failed_result.get('output', '')}"
        )
    if quality and quality.get("findings"):
        finding_lines = [
            f"- {item.get('severity')} {item.get('file')}: {item.get('message')}"
            for item in quality["findings"]
        ]
        sections.append("Quality findings:\n" + "\n".join(finding_lines))
    if security and security.get("findings"):
        finding_lines = [
            f"- {item.get('severity')} {item.get('file')}: {item.get('message')}"
            for item in security["findings"]
        ]
        sections.append("Security findings:\n" + "\n".join(finding_lines))
    return "\n\n".join(sections)


def create_build_run(project_id: int, project_path: str, stack: str, branch_name: str = "") -> BuildRun:
    db = SessionLocal()
    try:
        run = BuildRun(
            project_id=project_id,
            project_path=project_path,
            stack=stack,
            branch_name=branch_name,
            status="RUNNING",
        )
        db.add(run)
        db.commit()
        db.refresh(run)
        return run
    finally:
        db.close()


def complete_build_run(build_run_id: int, status: str, command: str, output: str, exit_code: int) -> BuildRun | None:
    db = SessionLocal()
    try:
        run = db.query(BuildRun).filter(BuildRun.id == build_run_id).first()
        if run is None:
            return None
        run.status = status
        run.command = command
        run.output_text = output
        run.exit_code = exit_code
        run.completed_at = datetime.utcnow()
        db.commit()
        db.refresh(run)
        return run
    finally:
        db.close()


def list_build_runs(project_id: int | None = None):
    db = SessionLocal()
    try:
        query = db.query(BuildRun)
        if project_id is not None:
            query = query.filter(BuildRun.project_id == project_id)
        return query.order_by(BuildRun.created_at.desc()).all()
    finally:
        db.close()


def project_path_for(project: Project, project_path: str | None = None) -> str:
    if project_path:
        return project_path
    if project.project_path:
        return project.project_path
    return str(resolve_output_dir(project.name))


def run_project_build(
    project_id: int,
    project_path: str | None = None,
    stack: str | None = None,
    create_fix_task: bool = True,
) -> dict | None:
    db = SessionLocal()
    try:
        project = db.query(Project).filter(Project.id == project_id).first()
        if project is None:
            return None
        path = project_path_for(project, project_path)
    finally:
        db.close()

    detected_stack = stack or detect_stack(path)
    branch_name = current_branch_for_path(path)
    build_run = create_build_run(project_id, path, detected_stack, branch_name)
    commands = build_commands(detected_stack, path)
    command_results = []

    for item in commands:
        cwd = Path(item["cwd"])
        if not cwd.exists():
            command_results.append({
                "command": " ".join(item["command"]),
                "cwd": str(cwd),
                "exit_code": 1,
                "output": f"Working directory does not exist: {cwd}",
            })
            break

        result = run_command(item["command"], str(cwd))
        result["cwd"] = str(cwd)
        command_results.append(result)
        if result["exit_code"] != 0:
            break

    quality = audit_python_project(project_id)
    if quality and quality["status"] == "FAIL":
        command_results.append({
            "command": "wacko quality review",
            "cwd": path,
            "exit_code": 1,
            "output": json.dumps(quality["findings"], indent=2),
            "timed_out": False,
        })

    security = scan_project_security(project_id)
    blocking_security = security and any(
        item.get("severity") in {"CRITICAL", "HIGH"} for item in security.get("findings", [])
    )
    if blocking_security:
        command_results.append({
            "command": "wacko security review",
            "cwd": path,
            "exit_code": 1,
            "output": json.dumps(security["findings"], indent=2),
            "timed_out": False,
        })

    failed = next((result for result in command_results if result["exit_code"] != 0), None)
    status = "FAILED" if failed else "PASSED"
    last = failed or command_results[-1]
    output = json.dumps(command_results, indent=2)
    completed = complete_build_run(build_run.id, status, last["command"], output, last["exit_code"])

    fix_task = None
    if failed and create_fix_task:
        fix_agent = choose_fix_agent(detected_stack, failed, quality, security)
        fix_summary = format_fix_summary(failed, quality, security)
        fix_task = TaskService.create_task(
            project_id,
            "Fix failing build/test run",
            (
                f"Build/test failed for project path:\n{path}\n\n"
                f"Detected stack: {detected_stack}\n\n"
                f"Assigned fix agent: {fix_agent}\n\n"
                "Failure log:\n"
                f"{output}\n\n"
                "Focused fix summary:\n"
                f"{fix_summary}\n\n"
                "If the failure includes Wacko quality review findings, fix those exact findings first.\n"
                "If the failure includes Wacko security review findings, fix high-severity security issues before cosmetic work.\n"
                "Study the project and update the files needed to make the build/test pass."
            ),
            assigned_agent=fix_agent,
            priority="HIGH",
            requires_approval=True,
        )

    return {
        "id": completed.id if completed else build_run.id,
        "project_id": project_id,
        "status": status,
        "stack": detected_stack,
        "project_path": path,
        "branch_name": branch_name,
        "commands": command_results,
        "fix_task_id": fix_task.id if fix_task else None,
    }
