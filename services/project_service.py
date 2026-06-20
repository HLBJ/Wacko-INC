from database.db import SessionLocal
from database.models import Project


class ProjectService:

    @staticmethod
    def create_project(name, description):
        db = SessionLocal()
        try:
            project = Project(
                name=name,
                description=description,
                status="ACTIVE"
            )
            db.add(project)
            db.commit()
            db.refresh(project)
            return project
        finally:
            db.close()

    @staticmethod
    def list_projects():
        db = SessionLocal()
        try:
            return db.query(Project).order_by(Project.created_at.desc()).all()
        finally:
            db.close()

    @staticmethod
    def get_project(project_id):
        db = SessionLocal()
        try:
            return db.query(Project).filter(Project.id == project_id).first()
        finally:
            db.close()
