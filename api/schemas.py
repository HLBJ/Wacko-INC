from typing import Optional

from pydantic import BaseModel


class ProjectCreate(BaseModel):
    name: str
    description: str = ""
    project_path: Optional[str] = None


class OpportunityCreate(BaseModel):
    title: str
    problem: str = ""
    target_customer: str = ""
    proposed_solution: str = ""


class OpportunityUpdate(BaseModel):
    title: Optional[str] = None
    problem: Optional[str] = None
    target_customer: Optional[str] = None
    proposed_solution: Optional[str] = None
    status: Optional[str] = None
    validation_notes: Optional[str] = None


class FinanceEntryCreate(BaseModel):
    project_id: Optional[int] = None
    entry_type: str = "EXPENSE"
    category: str = ""
    description: str = ""
    amount: float
    currency: str = "ZAR"


class MetricEntryCreate(BaseModel):
    project_id: Optional[int] = None
    metric_name: str
    metric_value: int
    unit: str = "count"
    source: str = "manual"
    notes: str = ""


class TaskCreate(BaseModel):
    project_id: int
    milestone_id: Optional[int] = None
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
    email_dry_run: Optional[bool] = None
    admin_email: Optional[str] = None
    smtp_host: Optional[str] = None
    smtp_port: Optional[int] = None
    smtp_username: Optional[str] = None
    smtp_password: Optional[str] = None
    smtp_from_email: Optional[str] = None


class EmailQueueCreate(BaseModel):
    project_id: Optional[int] = None
    support_ticket_id: Optional[int] = None
    to_email: str
    subject: str
    body: str


class SupportTicketCreate(BaseModel):
    project_id: Optional[int] = None
    sender_email: str = ""
    subject: str
    body: str


class SupportTicketUpdate(BaseModel):
    status: Optional[str] = None
    suggested_reply: Optional[str] = None


class KnowledgeArticleCreate(BaseModel):
    project_id: Optional[int] = None
    title: str
    body: str
    tags: str = ""


class KnowledgeArticleUpdate(BaseModel):
    title: Optional[str] = None
    body: Optional[str] = None
    tags: Optional[str] = None
    status: Optional[str] = None


class MilestoneUpdate(BaseModel):
    name: Optional[str] = None
    goal: Optional[str] = None
    status: Optional[str] = None
    sort_order: Optional[int] = None
    acceptance_criteria: Optional[str] = None


class GitActionCreate(BaseModel):
    project_path: Optional[str] = None
    message: Optional[str] = "Wacko Inc agent changes"


class BranchActionCreate(BaseModel):
    branch_name: str
    project_path: Optional[str] = None
