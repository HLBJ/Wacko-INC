from pathlib import Path

from database.db import SessionLocal
from database.models import Milestone, Project, Task
from services.file_writer import resolve_output_dir, safe_project_path
from services.system_blueprint import ensure_project_blueprint


DEFAULT_MILESTONES = [
    {
        "name": "MVP Foundation",
        "goal": "Create the smallest usable product with core records, navigation, and local build/test flow.",
        "acceptance_criteria": "Core project structure exists; basic user workflow is implemented; build/test can run locally.",
    },
    {
        "name": "Operational Workflow",
        "goal": "Implement the main business workflow for the selected system domain.",
        "acceptance_criteria": "Primary records can be created, updated, searched, and reviewed through the app.",
    },
    {
        "name": "Quality and Security Hardening",
        "goal": "Add tests, security fixes, validation, and release checks.",
        "acceptance_criteria": "Build passes; quality/security reviews have no blocking findings; CEO approvals are resolved.",
    },
    {
        "name": "Release Candidate",
        "goal": "Prepare a reviewable version that can be used by the first real user.",
        "acceptance_criteria": "CEO report is ready; support/known issues are documented; backup exists.",
    },
]


DOMAIN_MILESTONE = {
    "crm": {
        "name": "CRM Sales Pipeline",
        "goal": "Deliver contact, lead, activity, and pipeline management.",
        "acceptance_criteria": "A user can manage contacts/leads and move opportunities through pipeline stages.",
    },
    "booking": {
        "name": "Booking Flow",
        "goal": "Deliver customer booking, availability, and appointment management.",
        "acceptance_criteria": "A customer can request an appointment and staff can manage the schedule.",
    },
    "commerce": {
        "name": "Commerce Flow",
        "goal": "Deliver product catalog, cart/order flow, and admin order review.",
        "acceptance_criteria": "A user can browse products and create an order for admin review.",
    },
    "support": {
        "name": "Support Operations",
        "goal": "Deliver ticket intake, triage, reply drafts, and escalation workflow.",
        "acceptance_criteria": "A support user can triage a ticket, draft a reply, and escalate unresolved issues.",
    },
}


def default_milestones_for_project(project_id: int) -> list[dict] | None:
    blueprint_result = ensure_project_blueprint(project_id, overwrite=False)
    if blueprint_result is None:
        return None
    domain = blueprint_result["blueprint"].get("domain", "custom_software")
    milestones = list(DEFAULT_MILESTONES)
    if domain in DOMAIN_MILESTONE:
        milestones.insert(1, DOMAIN_MILESTONE[domain])
    return milestones


def ensure_project_roadmap(project_id: int, overwrite: bool = False) -> dict | None:
    db = SessionLocal()
    try:
        project = db.query(Project).filter(Project.id == project_id).first()
        if project is None:
            return None
        existing = db.query(Milestone).filter(Milestone.project_id == project_id).count()
        if existing and not overwrite:
            return {
                "project_id": project_id,
                "created": 0,
                "milestones": list_milestones(project_id),
            }
        if overwrite:
            db.query(Milestone).filter(Milestone.project_id == project_id).delete()
            db.commit()
    finally:
        db.close()

    defaults = default_milestones_for_project(project_id)
    if defaults is None:
        return None

    created = []
    db = SessionLocal()
    try:
        for index, item in enumerate(defaults, start=1):
            milestone = Milestone(
                project_id=project_id,
                name=item["name"],
                goal=item["goal"],
                acceptance_criteria=item["acceptance_criteria"],
                sort_order=index,
            )
            db.add(milestone)
            created.append(milestone)
        db.commit()
        for milestone in created:
            db.refresh(milestone)
        return {
            "project_id": project_id,
            "created": len(created),
            "milestones": created,
        }
    finally:
        db.close()


def list_milestones(project_id: int | None = None):
    db = SessionLocal()
    try:
        query = db.query(Milestone)
        if project_id is not None:
            query = query.filter(Milestone.project_id == project_id)
        return query.order_by(Milestone.project_id, Milestone.sort_order, Milestone.created_at).all()
    finally:
        db.close()


def update_milestone(milestone_id: int, payload: dict):
    db = SessionLocal()
    try:
        milestone = db.query(Milestone).filter(Milestone.id == milestone_id).first()
        if milestone is None:
            return None
        for key in ("name", "goal", "status", "sort_order", "acceptance_criteria"):
            if key in payload and payload[key] is not None:
                setattr(milestone, key, payload[key])
        db.commit()
        db.refresh(milestone)
        return milestone
    finally:
        db.close()


def assign_tasks_to_milestones(project_id: int) -> dict | None:
    milestones = list_milestones(project_id)
    if not milestones:
        roadmap = ensure_project_roadmap(project_id)
        if roadmap is None:
            return None
        milestones = roadmap["milestones"]

    def choose_milestone(task: Task):
        text = f"{task.title}\n{task.description}\n{task.assigned_agent}".lower()
        for milestone in milestones:
            name = milestone.name.lower()
            if "quality" in name and any(token in text for token in ["test", "security", "quality", "review"]):
                return milestone
            if "release" in name and any(token in text for token in ["release", "report", "backup", "approval"]):
                return milestone
            if any(token in text for token in ["frontend", "backend", "database", "api", "ui", "workflow", "implement", "build"]):
                if milestone.sort_order == 2:
                    return milestone
        return milestones[0]

    db = SessionLocal()
    assigned = 0
    try:
        tasks = db.query(Task).filter(Task.project_id == project_id, Task.milestone_id.is_(None)).all()
        milestone_by_id = {milestone.id: milestone for milestone in milestones}
        for task in tasks:
            chosen = choose_milestone(task)
            if chosen and chosen.id in milestone_by_id:
                task.milestone_id = chosen.id
                assigned += 1
        db.commit()
        return {
            "project_id": project_id,
            "assigned": assigned,
            "remaining_unassigned": db.query(Task).filter(Task.project_id == project_id, Task.milestone_id.is_(None)).count(),
        }
    finally:
        db.close()


def save_project_roadmap(project_id: int) -> dict | None:
    db = SessionLocal()
    try:
        project = db.query(Project).filter(Project.id == project_id).first()
        if project is None:
            return None
        project_dir = project.project_path or str(resolve_output_dir(project.name))
        project_name = project.name
    finally:
        db.close()

    milestones = list_milestones(project_id)
    if not milestones:
        result = ensure_project_roadmap(project_id)
        if result is None:
            return None
        milestones = result["milestones"]

    lines = [
        f"# {project_name} Roadmap",
        "",
        "## Milestones",
    ]
    for milestone in milestones:
        lines.extend([
            "",
            f"### {milestone.sort_order}. {milestone.name}",
            f"Status: {milestone.status}",
            "",
            milestone.goal,
            "",
            "Acceptance criteria:",
            milestone.acceptance_criteria,
        ])

    root = Path(project_dir).resolve()
    path = safe_project_path(root, "ROADMAP.md")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {
        "project_id": project_id,
        "roadmap_path": str(path),
        "milestones": milestones,
    }
