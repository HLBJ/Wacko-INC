import smtplib
from datetime import datetime
from email.message import EmailMessage

from database.db import SessionLocal
from database.models import EmailOutbox
from services.settings_service import get_settings


def queue_email(
    to_email: str,
    subject: str,
    body: str,
    project_id: int | None = None,
    support_ticket_id: int | None = None,
):
    db = SessionLocal()
    try:
        item = EmailOutbox(
            project_id=project_id,
            support_ticket_id=support_ticket_id,
            to_email=to_email,
            subject=subject,
            body=body,
            status="QUEUED",
        )
        db.add(item)
        db.commit()
        db.refresh(item)
        return item
    finally:
        db.close()


def list_outbox(status: str | None = None, project_id: int | None = None, limit: int = 200):
    db = SessionLocal()
    try:
        query = db.query(EmailOutbox)
        if status:
            query = query.filter(EmailOutbox.status == status)
        if project_id is not None:
            query = query.filter(EmailOutbox.project_id == project_id)
        return query.order_by(EmailOutbox.created_at.desc()).limit(limit).all()
    finally:
        db.close()


def _mark_email(email_id: int, status: str, error_text: str = ""):
    db = SessionLocal()
    try:
        item = db.query(EmailOutbox).filter(EmailOutbox.id == email_id).first()
        if item is None:
            return None
        item.status = status
        item.error_text = error_text
        if status in {"SENT", "DRY_RUN"}:
            item.sent_at = datetime.utcnow()
        db.commit()
        db.refresh(item)
        return item
    finally:
        db.close()


def send_email(email_id: int):
    db = SessionLocal()
    try:
        item = db.query(EmailOutbox).filter(EmailOutbox.id == email_id).first()
        if item is None:
            return None
        snapshot = {
            "id": item.id,
            "to_email": item.to_email,
            "subject": item.subject,
            "body": item.body,
        }
    finally:
        db.close()

    settings = get_settings()
    if settings.get("email_dry_run", True):
        return _mark_email(email_id, "DRY_RUN")

    host = settings.get("smtp_host")
    username = settings.get("smtp_username")
    password = settings.get("smtp_password")
    from_email = settings.get("smtp_from_email") or username
    if not host or not from_email:
        return _mark_email(email_id, "FAILED", "SMTP host and from email must be configured.")

    message = EmailMessage()
    message["To"] = snapshot["to_email"]
    message["From"] = from_email
    message["Subject"] = snapshot["subject"]
    message.set_content(snapshot["body"])

    try:
        with smtplib.SMTP(host, int(settings.get("smtp_port") or 587), timeout=30) as smtp:
            smtp.starttls()
            if username and password:
                smtp.login(username, password)
            smtp.send_message(message)
    except Exception as exc:
        return _mark_email(email_id, "FAILED", str(exc))

    return _mark_email(email_id, "SENT")


def send_queued(limit: int = 25) -> list:
    queued = list_outbox(status="QUEUED", limit=limit)
    results = []
    for item in queued:
        results.append(send_email(item.id))
    return results
