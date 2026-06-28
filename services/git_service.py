from pathlib import Path
import re

from database.db import SessionLocal
from database.models import Project
from services.command_runner import run_command
from services.file_writer import resolve_output_dir


def project_path_for(project_id: int, project_path: str | None = None) -> str | None:
    db = SessionLocal()
    try:
        project = db.query(Project).filter(Project.id == project_id).first()
        if project is None:
            return None
        if project_path:
            return project_path
        if project.project_path:
            return project.project_path
        return str(resolve_output_dir(project.name))
    finally:
        db.close()


def ensure_project_dir(path: str) -> Path:
    root = Path(path).resolve()
    if not root.exists() or not root.is_dir():
        raise ValueError(f"Project directory does not exist: {path}")
    return root


def git_available(root: Path) -> bool:
    return (root / ".git").exists()


def slug_branch(value: str) -> str:
    value = value.strip().lower()
    value = re.sub(r"[^a-z0-9._/-]+", "-", value)
    value = re.sub(r"-+", "-", value).strip("-/")
    return value or "work"


def current_branch_for_path(project_path: str) -> str:
    root = ensure_project_dir(project_path)
    if not git_available(root):
        return ""
    result = run_command(["git", "branch", "--show-current"], str(root))
    return result["output"].strip()


def default_branch(root: Path) -> str:
    branch = current_branch_for_path(str(root))
    return branch or "main"


def init_repo(project_id: int, project_path: str | None = None) -> dict | None:
    path = project_path_for(project_id, project_path)
    if path is None:
        return None
    root = ensure_project_dir(path)
    result = run_command(["git", "init"], str(root))
    if result["exit_code"] == 0:
        run_command(["git", "config", "user.name", "Wacko Inc OS"], str(root))
        run_command(["git", "config", "user.email", "wacko-inc-os@local"], str(root))
        run_command(["git", "checkout", "-B", "main"], str(root))
    return {
        "project_id": project_id,
        "project_path": str(root),
        "initialized": result["exit_code"] == 0,
        "output": result["output"],
    }


def status(project_id: int, project_path: str | None = None) -> dict | None:
    path = project_path_for(project_id, project_path)
    if path is None:
        return None
    root = ensure_project_dir(path)
    if not git_available(root):
        return {
            "project_id": project_id,
            "project_path": str(root),
            "is_repo": False,
            "status": "",
            "diff": "",
        }

    status_result = run_command(["git", "status", "--short"], str(root))
    diff_result = run_command(["git", "diff", "--", "."], str(root))
    staged_diff_result = run_command(["git", "diff", "--cached", "--", "."], str(root))
    return {
        "project_id": project_id,
        "project_path": str(root),
        "is_repo": True,
        "branch": current_branch_for_path(str(root)),
        "status": status_result["output"],
        "diff": diff_result["output"],
        "staged_diff": staged_diff_result["output"],
    }


def commit(project_id: int, message: str, project_path: str | None = None) -> dict | None:
    path = project_path_for(project_id, project_path)
    if path is None:
        return None
    root = ensure_project_dir(path)
    if not git_available(root):
        init_repo(project_id, str(root))

    add_result = run_command(["git", "add", "."], str(root))
    commit_result = run_command(["git", "commit", "-m", message or "Wacko Inc agent changes"], str(root))
    return {
        "project_id": project_id,
        "project_path": str(root),
        "add": add_result,
        "commit": commit_result,
        "committed": commit_result["exit_code"] == 0,
    }


def create_task_branch(project_id: int, task_id: int, agent_name: str, project_path: str | None = None) -> dict | None:
    path = project_path_for(project_id, project_path)
    if path is None:
        return None
    root = ensure_project_dir(path)
    if not git_available(root):
        init_repo(project_id, str(root))
        commit(project_id, "Initial project scaffold", str(root))

    branch_name = f"wacko/task-{task_id}-{slug_branch(agent_name)}"
    run_command(["git", "checkout", "-B", "main"], str(root))
    branch_result = run_command(["git", "checkout", "-B", branch_name], str(root))
    return {
        "project_id": project_id,
        "project_path": str(root),
        "branch_name": branch_name,
        "created": branch_result["exit_code"] == 0,
        "output": branch_result["output"],
    }


def checkout_branch(project_id: int, branch_name: str, project_path: str | None = None) -> dict | None:
    path = project_path_for(project_id, project_path)
    if path is None:
        return None
    root = ensure_project_dir(path)
    result = run_command(["git", "checkout", branch_name], str(root))
    return {
        "project_id": project_id,
        "project_path": str(root),
        "branch_name": branch_name,
        "checked_out": result["exit_code"] == 0,
        "output": result["output"],
    }


def merge_branch(project_id: int, branch_name: str, project_path: str | None = None) -> dict | None:
    path = project_path_for(project_id, project_path)
    if path is None:
        return None
    root = ensure_project_dir(path)
    if not git_available(root):
        return {"project_id": project_id, "merged": False, "output": "Project is not a Git repository."}

    checkout_main = run_command(["git", "checkout", "main"], str(root))
    merge_result = run_command(["git", "merge", "--no-ff", branch_name, "-m", f"Merge {branch_name}"], str(root))
    return {
        "project_id": project_id,
        "project_path": str(root),
        "branch_name": branch_name,
        "checkout_main": checkout_main,
        "merge": merge_result,
        "merged": checkout_main["exit_code"] == 0 and merge_result["exit_code"] == 0,
    }


def delete_branch(project_id: int, branch_name: str, project_path: str | None = None) -> dict | None:
    path = project_path_for(project_id, project_path)
    if path is None:
        return None
    root = ensure_project_dir(path)
    checkout_main = run_command(["git", "checkout", "main"], str(root))
    delete_result = run_command(["git", "branch", "-D", branch_name], str(root))
    return {
        "project_id": project_id,
        "project_path": str(root),
        "branch_name": branch_name,
        "checkout_main": checkout_main,
        "delete": delete_result,
        "deleted": delete_result["exit_code"] == 0,
    }


def commit_if_changed(project_id: int, message: str, project_path: str | None = None) -> dict | None:
    current = status(project_id, project_path)
    if current is None:
        return None
    if not current["is_repo"]:
        init_repo(project_id, current["project_path"])
        current = status(project_id, current["project_path"])

    has_changes = bool(current.get("status", "").strip())
    if not has_changes:
        return {
            "project_id": project_id,
            "project_path": current["project_path"],
            "committed": False,
            "message": "No changes to commit.",
            "status": current,
        }

    result = commit(project_id, message, current["project_path"])
    result["status_after"] = status(project_id, current["project_path"])
    return result


def revert_uncommitted(project_id: int, project_path: str | None = None) -> dict | None:
    current = status(project_id, project_path)
    if current is None:
        return None
    if not current["is_repo"]:
        return {
            "project_id": project_id,
            "project_path": current["project_path"],
            "reverted": False,
            "message": "Project is not a Git repository.",
            "status_before": current,
        }

    restore_result = run_command(["git", "restore", "--staged", "--worktree", "."], current["project_path"])
    clean_result = run_command(["git", "clean", "-fd", "--", "."], current["project_path"])
    after = status(project_id, current["project_path"])
    return {
        "project_id": project_id,
        "project_path": current["project_path"],
        "reverted": restore_result["exit_code"] == 0 and clean_result["exit_code"] == 0,
        "restore": restore_result,
        "clean": clean_result,
        "status_before": current,
        "status_after": after,
    }
