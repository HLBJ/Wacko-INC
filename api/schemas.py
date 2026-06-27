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
    output_dir: Optional[str] = None
    """
    Directory where agent output files will be written.
    Defaults to C:/Projects/<project_name> when omitted.
    You can also set OUTPUT_BASE_DIR in your .env to change the base globally.
    """
