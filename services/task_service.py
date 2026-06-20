from datetime import datetime

from database.db import SessionLocal
from database.models import AgentRun, Approval, Task


class TaskService:

    @staticmethod
    def create_task(
        project_id,
        title,
        description,
        assigned_agent="manager",
        priority="MEDIUM",
        requires_approval=True
    ):
        db = SessionLocal()
        try:
            task = Task(
                project_id=project_id,
                title=title,
                description=description,
                assigned_agent=assigned_agent,
                priority=priority,
                requires_approval=1 if requires_approval else 0
            )
            db.add(task)
            db.commit()
            db.refresh(task)
            return task
        finally:
            db.close()

    @staticmethod
    def list_tasks(project_id=None):
        db = SessionLocal()
        try:
            query = db.query(Task)
            if project_id is not None:
                query = query.filter(Task.project_id == project_id)
            return query.order_by(Task.created_at.desc()).all()
        finally:
            db.close()

    @staticmethod
    def update_status(task_id, status):
        db = SessionLocal()
        try:
            task = db.query(Task).filter(Task.id == task_id).first()
            if task is None:
                return None
            task.status = status
            db.commit()
            db.refresh(task)
            return task
        finally:
            db.close()

    @staticmethod
    def create_run(task_id, agent_name, input_text):
        db = SessionLocal()
        try:
            run = AgentRun(
                task_id=task_id,
                agent_name=agent_name,
                status="RUNNING",
                input_text=input_text
            )
            db.add(run)
            db.commit()
            db.refresh(run)
            return run
        finally:
            db.close()

    @staticmethod
    def complete_run(run_id, output_text, status="COMPLETED"):
        db = SessionLocal()
        try:
            run = db.query(AgentRun).filter(AgentRun.id == run_id).first()
            if run is None:
                return None
            run.status = status
            run.output_text = output_text
            run.completed_at = datetime.utcnow()
            db.commit()
            db.refresh(run)
            return run
        finally:
            db.close()

    @staticmethod
    def list_runs(task_id=None):
        db = SessionLocal()
        try:
            query = db.query(AgentRun)
            if task_id is not None:
                query = query.filter(AgentRun.task_id == task_id)
            return query.order_by(AgentRun.created_at.desc()).all()
        finally:
            db.close()

    @staticmethod
    def create_approval(task_id, title, reason):
        db = SessionLocal()
        try:
            approval = Approval(task_id=task_id, title=title, reason=reason)
            db.add(approval)
            db.commit()
            db.refresh(approval)
            return approval
        finally:
            db.close()

    @staticmethod
    def decide_approval(approval_id, status, notes=""):
        db = SessionLocal()
        try:
            approval = db.query(Approval).filter(Approval.id == approval_id).first()
            if approval is None:
                return None
            approval.status = status
            approval.decision_notes = notes
            approval.decided_at = datetime.utcnow()
            db.commit()
            db.refresh(approval)
            return approval
        finally:
            db.close()

    @staticmethod
    def list_approvals():
        db = SessionLocal()
        try:
            return db.query(Approval).order_by(Approval.created_at.desc()).all()
        finally:
            db.close()
