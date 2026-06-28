from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from database.db import Base


class Project(Base):
    __tablename__ = "projects"

    id = Column(Integer, primary_key=True)
    name = Column(String)
    description = Column(Text)
    project_path = Column(Text, default="")
    status = Column(String, default="ACTIVE")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    tasks = relationship("Task", back_populates="project", cascade="all, delete-orphan")
    build_runs = relationship("BuildRun", back_populates="project", cascade="all, delete-orphan")


class Task(Base):
    __tablename__ = "tasks"

    id = Column(Integer, primary_key=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    title = Column(String, nullable=False)
    description = Column(Text, default="")
    status = Column(String, default="BACKLOG")
    priority = Column(String, default="MEDIUM")
    assigned_agent = Column(String, default="manager")
    requires_approval = Column(Integer, default=1)
    branch_name = Column(String, default="")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    project = relationship("Project", back_populates="tasks")
    runs = relationship("AgentRun", back_populates="task", cascade="all, delete-orphan")
    approvals = relationship("Approval", back_populates="task", cascade="all, delete-orphan")


class AgentRun(Base):
    __tablename__ = "agent_runs"

    id = Column(Integer, primary_key=True)
    task_id = Column(Integer, ForeignKey("tasks.id"), nullable=False)
    agent_name = Column(String, nullable=False)
    status = Column(String, default="PENDING")
    input_text = Column(Text, default="")
    output_text = Column(Text, default="")
    output_file = Column(Text, default="")
    output_files = Column(Text, default="")
    branch_name = Column(String, default="")
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)

    task = relationship("Task", back_populates="runs")


class Approval(Base):
    __tablename__ = "approvals"

    id = Column(Integer, primary_key=True)
    task_id = Column(Integer, ForeignKey("tasks.id"), nullable=False)
    title = Column(String, nullable=False)
    reason = Column(Text, default="")
    status = Column(String, default="PENDING")
    decision_notes = Column(Text, default="")
    created_at = Column(DateTime, default=datetime.utcnow)
    decided_at = Column(DateTime, nullable=True)

    task = relationship("Task", back_populates="approvals")


class Execution(Base):
    __tablename__ = "executions"

    id = Column(Integer, primary_key=True)
    stage = Column(String)
    input_text = Column(Text)
    output_text = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)


class BuildRun(Base):
    __tablename__ = "build_runs"

    id = Column(Integer, primary_key=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    status = Column(String, default="PENDING")
    stack = Column(String, default="auto")
    project_path = Column(Text, default="")
    branch_name = Column(String, default="")
    command = Column(Text, default="")
    output_text = Column(Text, default="")
    exit_code = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)

    project = relationship("Project", back_populates="build_runs")


class Job(Base):
    __tablename__ = "jobs"

    id = Column(Integer, primary_key=True)
    job_type = Column(String, default="")
    status = Column(String, default="PENDING")
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=True)
    task_id = Column(Integer, ForeignKey("tasks.id"), nullable=True)
    title = Column(String, default="")
    input_text = Column(Text, default="")
    output_text = Column(Text, default="")
    error_text = Column(Text, default="")
    payload_json = Column(Text, default="")
    process_id = Column(Integer, nullable=True)
    retry_of_job_id = Column(Integer, ForeignKey("jobs.id"), nullable=True)
    cancel_requested = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)


class JobEvent(Base):
    __tablename__ = "job_events"

    id = Column(Integer, primary_key=True)
    job_id = Column(Integer, ForeignKey("jobs.id"), nullable=False)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=True)
    level = Column(String, default="INFO")
    message = Column(Text, default="")
    data_json = Column(Text, default="")
    created_at = Column(DateTime, default=datetime.utcnow)


class Setting(Base):
    __tablename__ = "settings"

    id = Column(Integer, primary_key=True)
    key = Column(String, unique=True, nullable=False)
    value = Column(Text, default="")
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class SupportTicket(Base):
    __tablename__ = "support_tickets"

    id = Column(Integer, primary_key=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=True)
    sender_email = Column(String, default="")
    subject = Column(String, default="")
    body = Column(Text, default="")
    category = Column(String, default="UNTRIAGED")
    priority = Column(String, default="MEDIUM")
    status = Column(String, default="NEW")
    suggested_reply = Column(Text, default="")
    created_task_id = Column(Integer, ForeignKey("tasks.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
