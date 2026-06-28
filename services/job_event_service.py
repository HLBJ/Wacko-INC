import json

from database.db import SessionLocal
from database.models import JobEvent


def record_job_event(job_id: int, project_id: int | None, message: str, level: str = "INFO", data: dict | None = None):
    db = SessionLocal()
    try:
        event = JobEvent(
            job_id=job_id,
            project_id=project_id,
            level=level,
            message=message,
            data_json=json.dumps(data or {}, default=str),
        )
        db.add(event)
        db.commit()
        db.refresh(event)
        return event
    finally:
        db.close()


def list_job_events(project_id: int | None = None, job_id: int | None = None, limit: int = 200):
    db = SessionLocal()
    try:
        query = db.query(JobEvent)
        if project_id is not None:
            query = query.filter(JobEvent.project_id == project_id)
        if job_id is not None:
            query = query.filter(JobEvent.job_id == job_id)
        return query.order_by(JobEvent.created_at.desc()).limit(limit).all()
    finally:
        db.close()
