import json
from datetime import datetime
from pathlib import Path

from services.file_writer import safe_project_path


MEMORY_PATH = ".wacko/project_memory.md"
HANDOFF_PATH = ".wacko/handoffs.jsonl"


def memory_file(project_dir: str) -> Path:
    root = Path(project_dir).resolve()
    return safe_project_path(root, MEMORY_PATH)


def handoff_file(project_dir: str) -> Path:
    root = Path(project_dir).resolve()
    return safe_project_path(root, HANDOFF_PATH)


def ensure_project_memory(project_dir: str, project_name: str) -> Path:
    path = memory_file(project_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_text(
            f"# {project_name} Project Memory\n\n"
            "## Operating Rules\n"
            "- Preserve working code unless the task explicitly requires replacing it.\n"
            "- Keep API schemas, persistence models, and service logic separated.\n"
            "- Update all dependent imports/usages when changing a shared file.\n"
            "- Prefer small, reviewable changes with clear handoffs.\n\n"
            "## Decisions\n"
            "- No major project decisions recorded yet.\n\n"
            "## Current Architecture\n"
            "- No architecture summary recorded yet.\n\n"
            "## Open Risks\n"
            "- No open risks recorded yet.\n\n",
            encoding="utf-8",
        )
    return path


def read_project_memory(project_dir: str, project_name: str, max_chars: int = 8000) -> str:
    path = ensure_project_memory(project_dir, project_name)
    return path.read_text(encoding="utf-8", errors="replace")[-max_chars:]


def read_recent_handoffs(project_dir: str, max_items: int = 8) -> str:
    path = handoff_file(project_dir)
    if not path.exists():
        return "No prior handoffs recorded."

    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    entries = []
    for line in lines[-max_items:]:
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue
        entries.append(
            f"- {item.get('created_at', '')} | {item.get('agent', '')} | "
            f"{item.get('task', '')}: {item.get('summary', '')}"
        )
    return "\n".join(entries) or "No prior handoffs recorded."


def parse_agent_summary(output: str) -> dict:
    stripped = output.strip()
    first = stripped.find("{")
    last = stripped.rfind("}")
    if first != -1 and last != -1 and first < last:
        try:
            payload = json.loads(stripped[first:last + 1])
        except json.JSONDecodeError:
            payload = {}
    else:
        payload = {}

    files = payload.get("files") if isinstance(payload.get("files"), list) else []
    return {
        "summary": str(payload.get("summary") or output[:500]).strip(),
        "files": [str(item.get("path")) for item in files if isinstance(item, dict) and item.get("path")],
        "assumptions": payload.get("assumptions") if isinstance(payload.get("assumptions"), list) else [],
        "risks": payload.get("risks") if isinstance(payload.get("risks"), list) else [],
    }


def append_handoff(
    project_dir: str,
    task_title: str,
    agent_name: str,
    output: str,
    generated_files: list[str] | None = None,
) -> dict:
    parsed = parse_agent_summary(output)
    entry = {
        "created_at": datetime.utcnow().isoformat(),
        "agent": agent_name,
        "task": task_title,
        "summary": parsed["summary"][:1000],
        "declared_files": parsed["files"],
        "generated_files": generated_files or [],
        "assumptions": parsed["assumptions"],
        "risks": parsed["risks"],
    }

    path = handoff_file(project_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry) + "\n")
    return entry


def update_project_memory(
    project_dir: str,
    project_name: str,
    task_title: str,
    agent_name: str,
    output: str,
    generated_files: list[str] | None = None,
) -> Path:
    path = ensure_project_memory(project_dir, project_name)
    parsed = parse_agent_summary(output)
    relative_files = []
    root = Path(project_dir).resolve()
    for item in generated_files or []:
        try:
            relative_files.append(str(Path(item).resolve().relative_to(root)).replace("\\", "/"))
        except ValueError:
            relative_files.append(item)

    lines = [
        "",
        "## Latest Agent Handoff",
        f"- Time: {datetime.utcnow().isoformat()}",
        f"- Agent: {agent_name}",
        f"- Task: {task_title}",
        f"- Summary: {parsed['summary'][:1000]}",
    ]
    if relative_files:
        lines.append(f"- Files changed: {', '.join(relative_files)}")
    if parsed["assumptions"]:
        lines.append(f"- Assumptions: {'; '.join(map(str, parsed['assumptions']))}")
    if parsed["risks"]:
        lines.append(f"- Risks: {'; '.join(map(str, parsed['risks']))}")

    with path.open("a", encoding="utf-8") as handle:
        handle.write("\n".join(lines) + "\n")
    return path
