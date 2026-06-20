from typing import Optional

from pydantic import BaseModel


class ProjectCreate(BaseModel):
    name: str
    description: str = ""


class TaskCreate(BaseModel):
    project_id: int
    title: str
    description: str = ""
    assigned_agent: str = "manager"
    priority: str = "MEDIUM"
    requires_approval: bool = True


class ApprovalDecision(BaseModel):
    status: str
    notes: Optional[str] = ""


class CompanyGoalCreate(BaseModel):
    goal: str
    auto_start: bool = True
