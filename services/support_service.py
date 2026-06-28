from database.db import SessionLocal
from database.models import SupportTicket
from services.task_service import TaskService


CATEGORY_RULES = [
    ("SECURITY", ["security", "hack", "breach", "vulnerability", "password leaked", "data leak"], "security", "HIGH"),
    ("BUG", ["bug", "error", "crash", "broken", "failed", "does not work", "exception"], "backend", "HIGH"),
    ("ACCESS", ["login", "password", "account", "permission", "access", "auth"], "backend", "HIGH"),
    ("FEATURE", ["feature", "request", "could you add", "enhancement", "would like"], "manager", "MEDIUM"),
    ("PERFORMANCE", ["slow", "timeout", "performance", "lag", "takes long"], "testing", "MEDIUM"),
    ("UI", ["screen", "button", "layout", "page", "mobile", "display"], "frontend", "MEDIUM"),
]


def classify_ticket(subject: str, body: str) -> dict:
    text = f"{subject}\n{body}".lower()
    for category, terms, agent, priority in CATEGORY_RULES:
        if any(term in text for term in terms):
            return {
                "category": category,
                "assigned_agent": agent,
                "priority": priority,
            }
    return {
        "category": "QUESTION",
        "assigned_agent": "support",
        "priority": "LOW",
    }


def draft_reply(ticket: SupportTicket, category: str) -> str:
    greeting = "Hi"
    subject = ticket.subject or "your request"
    if category in {"BUG", "ACCESS", "SECURITY", "PERFORMANCE", "UI"}:
        return (
            f"{greeting},\n\n"
            f"Thanks for reporting this. We have logged your request about \"{subject}\" and will investigate it. "
            "If you can share screenshots, steps to reproduce, or the time the issue happened, that will help us resolve it faster.\n\n"
            "Regards,\nSupport"
        )
    if category == "FEATURE":
        return (
            f"{greeting},\n\n"
            f"Thanks for the suggestion about \"{subject}\". We have logged it for product review and will consider it for a future update.\n\n"
            "Regards,\nSupport"
        )
    return (
        f"{greeting},\n\n"
        f"Thanks for contacting us about \"{subject}\". We have received your message and will respond as soon as possible.\n\n"
        "Regards,\nSupport"
    )


def create_ticket(project_id: int | None, sender_email: str, subject: str, body: str):
    db = SessionLocal()
    try:
        ticket = SupportTicket(
            project_id=project_id,
            sender_email=sender_email,
            subject=subject,
            body=body,
        )
        db.add(ticket)
        db.commit()
        db.refresh(ticket)
        return ticket
    finally:
        db.close()


def list_tickets(project_id: int | None = None, status: str | None = None):
    db = SessionLocal()
    try:
        query = db.query(SupportTicket)
        if project_id is not None:
            query = query.filter(SupportTicket.project_id == project_id)
        if status:
            query = query.filter(SupportTicket.status == status)
        return query.order_by(SupportTicket.created_at.desc()).limit(200).all()
    finally:
        db.close()


def triage_ticket(ticket_id: int):
    db = SessionLocal()
    try:
        ticket = db.query(SupportTicket).filter(SupportTicket.id == ticket_id).first()
        if ticket is None:
            return None
        classification = classify_ticket(ticket.subject, ticket.body)
        ticket.category = classification["category"]
        ticket.priority = classification["priority"]
        ticket.status = "TRIAGED"
        ticket.suggested_reply = draft_reply(ticket, classification["category"])
        db.commit()
        db.refresh(ticket)
        return ticket
    finally:
        db.close()


def update_ticket(ticket_id: int, status: str | None = None, suggested_reply: str | None = None):
    db = SessionLocal()
    try:
        ticket = db.query(SupportTicket).filter(SupportTicket.id == ticket_id).first()
        if ticket is None:
            return None
        if status:
            ticket.status = status.upper()
        if suggested_reply is not None:
            ticket.suggested_reply = suggested_reply
        db.commit()
        db.refresh(ticket)
        return ticket
    finally:
        db.close()


def escalate_ticket(ticket_id: int):
    db = SessionLocal()
    try:
        ticket = db.query(SupportTicket).filter(SupportTicket.id == ticket_id).first()
        if ticket is None:
            return None
        classification = classify_ticket(ticket.subject, ticket.body)
        project_id = ticket.project_id
        if project_id is None:
            return {"ticket": ticket, "task": None, "error": "Ticket is not linked to a project."}
        task = TaskService.create_task(
            project_id=project_id,
            title=f"Support escalation: {ticket.subject}",
            description=(
                f"Support ticket #{ticket.id}\n"
                f"From: {ticket.sender_email}\n"
                f"Category: {classification['category']}\n\n"
                f"Customer message:\n{ticket.body}\n\n"
                "Investigate and update the project files if a product change is required."
            ),
            assigned_agent=classification["assigned_agent"],
            priority=classification["priority"],
            requires_approval=True,
        )
        ticket.category = classification["category"]
        ticket.priority = classification["priority"]
        ticket.status = "ESCALATED"
        ticket.created_task_id = task.id
        if not ticket.suggested_reply:
            ticket.suggested_reply = draft_reply(ticket, classification["category"])
        db.commit()
        db.refresh(ticket)
        return {"ticket": ticket, "task": task, "error": None}
    finally:
        db.close()
