from typing import Optional

from pydantic import BaseModel


class ProjectCreate(BaseModel):
    name: str
    description: str = ""
    project_path: Optional[str] = None


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
    stack: str = "auto"
    """
    Directory where agent output files will be written.
    Defaults to C:/Project/<project_name> when omitted.
    You can also set OUTPUT_BASE_DIR in your .env to change the base globally.
    """


class ProjectUpdateCreate(BaseModel):
    project_path: str
    instructions: str
    auto_start: bool = True


class BuildRunCreate(BaseModel):
    project_path: Optional[str] = None
    stack: Optional[str] = None
    auto_fix: bool = True
    max_fix_attempts: int = 3


class ProjectWorkflowCreate(BaseModel):
    workflow: str
    max_fix_attempts: Optional[int] = None
    max_cycles: Optional[int] = None
    overwrite_architecture: bool = False


class SettingsUpdate(BaseModel):
    output_base_dir: Optional[str] = None
    max_fix_attempts: Optional[int] = None
    max_autopilot_cycles: Optional[int] = None
    local_only: Optional[bool] = None
    auto_save_ceo_reports: Optional[bool] = None


class SupportTicketCreate(BaseModel):
    project_id: Optional[int] = None
    sender_email: str = ""
    subject: str
    body: str


class SupportTicketUpdate(BaseModel):
    status: Optional[str] = None
    suggested_reply: Optional[str] = None


class GitActionCreate(BaseModel):
    project_path: Optional[str] = None
    message: Optional[str] = "Wacko Inc agent changes"


class BranchActionCreate(BaseModel):
    branch_name: str
    project_path: Optional[str] = None
