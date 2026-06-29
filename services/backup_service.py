import shutil
from datetime import datetime
from pathlib import Path

from database.db import DATABASE_URL
from services.file_writer import safe_project_path
from services.settings_service import get_settings


def _sqlite_path() -> Path:
    if not DATABASE_URL.startswith("sqlite:///"):
        raise ValueError("Only SQLite backups are supported by the local backup service.")
    return Path(DATABASE_URL.replace("sqlite:///", "", 1)).resolve()


def backup_root() -> Path:
    settings = get_settings()
    root = Path(settings.get("output_base_dir") or "C:/Project").resolve()
    return safe_project_path(root, "_wacko_company/backups")


def create_backup() -> dict:
    source = _sqlite_path()
    if not source.exists():
        raise FileNotFoundError(str(source))

    target_dir = backup_root()
    target_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    target = safe_project_path(target_dir, f"wacko_backup_{timestamp}.db")
    shutil.copy2(source, target)
    return {
        "source": str(source),
        "backup_path": str(target),
        "created_at": datetime.utcnow().isoformat(),
        "size": target.stat().st_size,
    }


def list_backups() -> list[dict]:
    root = backup_root()
    if not root.exists():
        return []
    backups = []
    for path in sorted(root.glob("wacko_backup_*.db"), reverse=True):
        stat = path.stat()
        backups.append({
            "path": str(path),
            "size": stat.st_size,
            "modified": stat.st_mtime,
        })
    return backups
