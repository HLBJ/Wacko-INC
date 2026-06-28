import json
import os
import signal
import subprocess
from datetime import datetime

from database.db import SessionLocal
from database.models import Job


def create_job(
    job_type: str,
    title: str,
    project_id=None,
    task_id=None,
    input_text="",
    retry_of_job_id=None,
    payload=None,
) -> Job:
    db = SessionLocal()
    try:
        job = Job(
            job_type=job_type,
            title=title,
            project_id=project_id,
            task_id=task_id,
            input_text=input_text,
            payload_json=json.dumps(payload or {}),
            retry_of_job_id=retry_of_job_id,
            status="PENDING",
        )
        db.add(job)
        db.commit()
        db.refresh(job)
        return job
    finally:
        db.close()


def set_process_id(job_id: int, process_id: int):
    db = SessionLocal()
    try:
        job = db.query(Job).filter(Job.id == job_id).first()
        if job is None:
            return None
        job.process_id = process_id
        db.commit()
        db.refresh(job)
        return job
    finally:
        db.close()


def mark_running(job_id: int):
    db = SessionLocal()
    try:
        job = db.query(Job).filter(Job.id == job_id).first()
        if job is None:
            return None
        if job.cancel_requested:
            job.status = "CANCELLED"
            job.completed_at = datetime.utcnow()
            db.commit()
            db.refresh(job)
            return job
        job.status = "RUNNING"
        job.started_at = datetime.utcnow()
        db.commit()
        db.refresh(job)
        return job
    finally:
        db.close()


def mark_completed(job_id: int, output_text: str = ""):
    db = SessionLocal()
    try:
        job = db.query(Job).filter(Job.id == job_id).first()
        if job is None:
            return None
        if job.cancel_requested:
            job.status = "CANCELLED"
            job.output_text = output_text
            job.completed_at = datetime.utcnow()
            db.commit()
            db.refresh(job)
            return job
        job.status = "COMPLETED"
        job.output_text = output_text
        job.completed_at = datetime.utcnow()
        db.commit()
        db.refresh(job)
        return job
    finally:
        db.close()


def mark_failed(job_id: int, error_text: str):
    db = SessionLocal()
    try:
        job = db.query(Job).filter(Job.id == job_id).first()
        if job is None:
            return None
        job.status = "FAILED"
        job.error_text = error_text
        job.completed_at = datetime.utcnow()
        db.commit()
        db.refresh(job)
        return job
    finally:
        db.close()


def cancel_job(job_id: int):
    db = SessionLocal()
    try:
        job = db.query(Job).filter(Job.id == job_id).first()
        if job is None:
            return None
        process_id = job.process_id
        job.cancel_requested = 1
        if job.status in {"PENDING", "RUNNING"}:
            job.status = "CANCELLED"
            job.completed_at = datetime.utcnow()
        db.commit()
        db.refresh(job)
        if process_id:
            terminate_process(process_id)
        return job
    finally:
        db.close()


def get_job(job_id: int):
    db = SessionLocal()
    try:
        return db.query(Job).filter(Job.id == job_id).first()
    finally:
        db.close()


def should_cancel(job_id: int) -> bool:
    db = SessionLocal()
    try:
        job = db.query(Job).filter(Job.id == job_id).first()
        return bool(job and job.cancel_requested)
    finally:
        db.close()


def job_payload(job: Job) -> dict:
    if not job.payload_json:
        return {}
    try:
        return json.loads(job.payload_json)
    except json.JSONDecodeError:
        return {}


def terminate_process(process_id: int):
    try:
        if os.name == "nt":
            subprocess.run(
                ["taskkill", "/PID", str(process_id), "/T", "/F"],
                capture_output=True,
                text=True,
                timeout=10,
            )
        else:
            os.kill(process_id, signal.SIGTERM)
    except Exception:
        pass


def list_jobs(project_id: int | None = None):
    db = SessionLocal()
    try:
        query = db.query(Job)
        if project_id is not None:
            query = query.filter(Job.project_id == project_id)
        return query.order_by(Job.created_at.desc()).limit(100).all()
    finally:
        db.close()
