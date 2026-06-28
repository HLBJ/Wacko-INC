from pathlib import Path

from database.db import SessionLocal
from database.models import Project
from services.file_writer import resolve_output_dir, safe_project_path
from services.project_reader import SKIP_DIRS, TEXT_EXTENSIONS


MAX_FILE_BYTES = 500_000


def project_root_for(project_id: int) -> Path | None:
    db = SessionLocal()
    try:
        project = db.query(Project).filter(Project.id == project_id).first()
        if project is None:
            return None
        return Path(project.project_path or resolve_output_dir(project.name)).resolve()
    finally:
        db.close()


def is_text_file(path: Path) -> bool:
    return path.suffix.lower() in TEXT_EXTENSIONS or path.name.lower() in {
        ".env",
        ".gitignore",
        "dockerfile",
    }


def list_project_files(project_id: int, include_notes: bool = True) -> dict | None:
    root = project_root_for(project_id)
    if root is None:
        return None
    if not root.exists() or not root.is_dir():
        return {
            "project_id": project_id,
            "project_path": str(root),
            "exists": False,
            "files": [],
        }

    files = []
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(root)
        parts = set(relative.parts)
        if not include_notes and ".wacko" in parts:
            continue
        if parts & (SKIP_DIRS - {".wacko"}):
            continue
        stat = path.stat()
        files.append({
            "path": str(relative).replace("\\", "/"),
            "size": stat.st_size,
            "modified": stat.st_mtime,
            "readable": is_text_file(path) and stat.st_size <= MAX_FILE_BYTES,
            "note": ".wacko" in parts,
        })

    return {
        "project_id": project_id,
        "project_path": str(root),
        "exists": True,
        "files": files,
    }


def read_project_file(project_id: int, relative_path: str) -> dict | None:
    root = project_root_for(project_id)
    if root is None:
        return None
    if not root.exists() or not root.is_dir():
        raise ValueError(f"Project directory does not exist: {root}")

    path = safe_project_path(root, relative_path)
    if not path.exists() or not path.is_file():
        raise FileNotFoundError(relative_path)
    if not is_text_file(path):
        raise ValueError(f"File is not a supported text file: {relative_path}")
    if path.stat().st_size > MAX_FILE_BYTES:
        raise ValueError(f"File is too large to preview: {relative_path}")

    return {
        "project_id": project_id,
        "project_path": str(root),
        "path": str(path.relative_to(root)).replace("\\", "/"),
        "content": path.read_text(encoding="utf-8", errors="replace"),
        "size": path.stat().st_size,
        "modified": path.stat().st_mtime,
    }
