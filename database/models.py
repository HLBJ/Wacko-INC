from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from database.db import Base


class Project(Base):
    __tablename__ = "projects"

    id = Column(Integer, primary_key=True)
    name = Column(String)
    description = Column(Text)
    status = Column(String, default="ACTIVE")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    tasks = relationship("Task", back_populates="project", cascade="all, delete-orphan")


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
