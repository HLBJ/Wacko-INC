import json
from datetime import datetime
from pathlib import Path

from services.file_writer import safe_project_path
from services.project_overview import project_overview
from services.system_blueprint import ensure_project_blueprint


def build_project_brief(project_id: int) -> dict | None:
    overview = project_overview(project_id)
    if overview is None:
        return None

    project = overview["project"]
    blueprint_result = ensure_project_blueprint(project_id, overwrite=False)
    blueprint = (blueprint_result or {}).get("blueprint") or {}
    next_action = overview.get("recommended_next_action") or {}

    lines = [
        f"# {project['name']} Project Brief",
        "",
        f"Generated: {datetime.utcnow().isoformat()} UTC",
        "",
        "## Purpose",
        project.get("description") or blueprint.get("goal") or "No project purpose recorded yet.",
        "",
        "## System Type",
        f"- Domain: {blueprint.get('domain', 'custom_software')}",
        f"- Stack: {overview.get('stack', 'unknown')}",
        "",
        "## Expected Modules",
    ]
    for module in blueprint.get("expected_modules", []):
        lines.append(f"- {module}")

    lines.extend(["", "## Operating Principles"])
    for principle in blueprint.get("product_principles", []):
        lines.append(f"- {principle}")

    lines.extend([
        "",
        "## Current Delivery State",
        f"- Architecture contract: {'Ready' if overview.get('architecture_ready') else 'Missing'}",
        f"- System blueprint: {'Ready' if overview.get('blueprint_ready') else 'Missing'}",
        f"- Latest build: {(overview.get('latest_build') or {}).get('status', 'NONE')}",
        f"- Pending approvals: {overview.get('pending_approvals', 0)}",
        f"- Open support tickets: {sum(count for status, count in (overview.get('support_counts') or {}).items() if status != 'CLOSED')}",
        "",
        "## Recommended Next Step",
        f"- {next_action.get('label', 'No recommendation')}: {next_action.get('reason', '')}",
    ])

    return {
        "project_id": project_id,
        "project_name": project["name"],
        "project_path": project.get("project_path") or "",
        "brief": "\n".join(lines) + "\n",
        "blueprint": blueprint,
    }


def save_project_brief(project_id: int) -> dict | None:
    brief = build_project_brief(project_id)
    if brief is None:
        return None
    root = Path(brief["project_path"]).resolve()
    brief_path = safe_project_path(root, "PROJECT_BRIEF.md")
    json_path = safe_project_path(root, ".wacko/project_brief.json")
    brief_path.write_text(brief["brief"], encoding="utf-8")
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps({
        "project_id": brief["project_id"],
        "project_name": brief["project_name"],
        "blueprint": brief["blueprint"],
    }, indent=2), encoding="utf-8")
    return {
        **brief,
        "brief_path": str(brief_path),
        "json_path": str(json_path),
    }
