from datetime import datetime

from pathlib import Path

from services.file_writer import safe_project_path
from services.project_overview import project_overview


def _line_items(items: list[str]) -> list[str]:
    return [f"- {item}" for item in items] if items else ["- None"]


def build_ceo_report(project_id: int) -> dict | None:
    overview = project_overview(project_id)
    if overview is None:
        return None

    project = overview["project"]
    quality = overview.get("quality") or {}
    security = overview.get("security") or {}
    latest_build = overview.get("latest_build") or {}
    next_action = overview.get("recommended_next_action") or {}

    blockers = []
    if not overview.get("project_exists"):
        blockers.append("Project path does not exist.")
    if not overview.get("architecture_ready"):
        blockers.append("Architecture contract is missing.")
    if latest_build.get("status") != "PASSED":
        blockers.append("Latest build/test run has not passed.")
    if quality.get("status") != "PASS":
        blockers.append("Quality review is not passing.")
    high_security = [
        item for item in security.get("findings", [])
        if item.get("severity") in {"CRITICAL", "HIGH"}
    ]
    if high_security:
        blockers.append(f"{len(high_security)} high-risk security finding(s) remain.")
    if overview.get("pending_approvals"):
        blockers.append(f"{overview['pending_approvals']} approval(s) are pending.")
    open_support = sum(
        count for status, count in (overview.get("support_counts") or {}).items()
        if status not in {"CLOSED"}
    )
    if open_support:
        blockers.append(f"{open_support} support ticket(s) are still open.")

    lines = [
        f"# CEO Project Report: {project['name']}",
        "",
        f"Generated: {datetime.utcnow().isoformat()} UTC",
        f"Project path: {project.get('project_path') or ''}",
        f"Stack: {overview.get('stack') or 'unknown'}",
        "",
        "## Readiness",
        f"- Project exists: {'Yes' if overview.get('project_exists') else 'No'}",
        f"- Architecture contract: {'Ready' if overview.get('architecture_ready') else 'Missing'}",
        f"- Latest build: {latest_build.get('status') or 'NONE'}",
        f"- Quality: {quality.get('status') or 'UNKNOWN'} ({len(quality.get('findings', []))} finding(s))",
        f"- Security: {security.get('status') or 'UNKNOWN'} ({len(security.get('findings', []))} finding(s))",
        f"- Pending approvals: {overview.get('pending_approvals', 0)}",
        f"- Open support tickets: {open_support}",
        "",
        "## Recommended Next Step",
        f"- {next_action.get('label', 'No recommendation')}: {next_action.get('reason', '')}",
        "",
        "## Blockers",
        *_line_items(blockers),
        "",
        "## Task Summary",
    ]

    task_counts = overview.get("task_counts") or {}
    lines.extend(_line_items([f"{status}: {count}" for status, count in sorted(task_counts.items())]))

    lines.extend(["", "## Support Summary"])
    support_counts = overview.get("support_counts") or {}
    lines.extend(_line_items([f"{status}: {count}" for status, count in sorted(support_counts.items())]))

    lines.extend(["", "## Agent Workload"])
    for agent in overview.get("agent_workload", []):
        latest_task = agent.get("latest_task") or {}
        task_text = f"{latest_task.get('status')}: {latest_task.get('title')}" if latest_task else "No current task"
        lines.append(f"- {agent['name']}: {agent.get('task_total', 0)} task(s). Latest: {task_text}")

    lines.extend(["", "## Quality Findings"])
    lines.extend(_line_items([
        f"{item.get('severity')} | {item.get('file')}: {item.get('message')}"
        for item in quality.get("findings", [])
    ]))

    lines.extend(["", "## Security Findings"])
    lines.extend(_line_items([
        f"{item.get('severity')} | {item.get('file')}: {item.get('message')}"
        for item in security.get("findings", [])
    ]))

    report = "\n".join(lines) + "\n"
    return {
        "project_id": project_id,
        "project_name": project["name"],
        "ready": not blockers,
        "blockers": blockers,
        "report": report,
        "project_path": project.get("project_path") or "",
    }


def save_ceo_report(project_id: int) -> dict | None:
    report = build_ceo_report(project_id)
    if report is None:
        return None

    root = Path(report["project_path"]).resolve()
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    report_path = safe_project_path(root, f".wacko/reports/ceo_report_{timestamp}.md")
    latest_path = safe_project_path(root, ".wacko/reports/latest_ceo_report.md")
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(report["report"], encoding="utf-8")
    latest_path.write_text(report["report"], encoding="utf-8")

    return {
        **report,
        "saved_path": str(report_path),
        "latest_path": str(latest_path),
    }
