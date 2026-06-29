from datetime import datetime
from pathlib import Path

from database.db import SessionLocal
from database.models import Approval, Job, Opportunity, Project, SupportTicket, Task
from services.file_writer import safe_project_path
from services.project_report import build_ceo_report
from services.settings_service import get_settings
from services.finance_service import finance_summary
from services.metric_service import metric_summary


def build_company_digest() -> dict:
    db = SessionLocal()
    try:
        projects = db.query(Project).order_by(Project.created_at.desc()).all()
        pending_approvals = db.query(Approval).filter(Approval.status == "PENDING").count()
        active_jobs = db.query(Job).filter(Job.status.in_(["PENDING", "RUNNING"])).count()
        open_support = db.query(SupportTicket).filter(SupportTicket.status != "CLOSED").count()
        open_tasks = db.query(Task).filter(~Task.status.in_(["DONE", "AWAITING_APPROVAL"])).count()
        open_opportunities = db.query(Opportunity).filter(Opportunity.status.in_(["IDEA", "VALIDATION", "APPROVED"])).count()
        project_ids = [project.id for project in projects]
    finally:
        db.close()

    project_reports = []
    for project_id in project_ids:
        report = build_ceo_report(project_id)
        if report:
            project_reports.append(report)
    finances = finance_summary(currency="ZAR")
    metrics = metric_summary()

    lines = [
        "# Wacko Inc CEO Digest",
        "",
        f"Generated: {datetime.utcnow().isoformat()} UTC",
        "",
        "## Company Snapshot",
        f"- Active projects: {len(project_reports)}",
        f"- Open tasks: {open_tasks}",
        f"- Open opportunities: {open_opportunities}",
        f"- Pending approvals: {pending_approvals}",
        f"- Active jobs: {active_jobs}",
        f"- Open support tickets: {open_support}",
        f"- Revenue: {finances['currency']} {finances['revenue']:.2f}",
        f"- Expenses: {finances['currency']} {finances['expenses']:.2f}",
        f"- Profit: {finances['currency']} {finances['profit']:.2f}",
        f"- Metric entries: {metrics['entry_count']}",
        "",
        "## Projects",
    ]

    if not project_reports:
        lines.append("- No projects yet.")
    for report in project_reports:
        status = "READY" if report["ready"] else "BLOCKED"
        blockers = "; ".join(report["blockers"]) if report["blockers"] else "No blockers"
        lines.append(f"- {report['project_name']}: {status}. {blockers}")

    digest = "\n".join(lines) + "\n"
    return {
        "ready_projects": len([report for report in project_reports if report["ready"]]),
        "blocked_projects": len([report for report in project_reports if not report["ready"]]),
        "pending_approvals": pending_approvals,
        "active_jobs": active_jobs,
        "open_support": open_support,
        "open_tasks": open_tasks,
        "open_opportunities": open_opportunities,
        "finance": finances,
        "metrics": metrics,
        "report": digest,
    }


def save_company_digest() -> dict:
    digest = build_company_digest()
    settings = get_settings()
    root = Path(settings.get("output_base_dir") or "C:/Project").resolve()
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    report_path = safe_project_path(root, f"_wacko_company/reports/company_digest_{timestamp}.md")
    latest_path = safe_project_path(root, "_wacko_company/reports/latest_company_digest.md")
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(digest["report"], encoding="utf-8")
    latest_path.write_text(digest["report"], encoding="utf-8")
    return {
        **digest,
        "saved_path": str(report_path),
        "latest_path": str(latest_path),
    }
