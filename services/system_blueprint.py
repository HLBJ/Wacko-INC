import json
from pathlib import Path

from database.db import SessionLocal
from database.models import Project
from services.file_writer import resolve_output_dir, safe_project_path


BLUEPRINT_JSON = ".wacko/system_blueprint.json"
BLUEPRINT_MD = "SYSTEM_BLUEPRINT.md"


DOMAIN_RULES = [
    ("support", ["support", "ticket", "helpdesk", "customer service", "inbox"]),
    ("crm", ["crm", "lead", "customer relationship", "sales pipeline"]),
    ("booking", ["booking", "appointment", "schedule", "reservation"]),
    ("commerce", ["shop", "store", "ecommerce", "payment", "checkout", "invoice"]),
    ("operations", ["inventory", "workflow", "approval", "internal tool", "dashboard"]),
    ("learning", ["course", "lesson", "training", "quiz", "student"]),
    ("content", ["blog", "cms", "publishing", "article", "media"]),
]


def infer_domain(goal: str) -> str:
    lowered = goal.lower()
    for domain, terms in DOMAIN_RULES:
        if any(term in lowered for term in terms):
            return domain
    return "custom_software"


def blueprint_for(project_name: str, goal: str, stack: str) -> dict:
    domain = infer_domain(goal)
    common_modules = [
        "authentication",
        "user_and_role_management",
        "audit_log",
        "settings",
        "dashboard",
        "notifications",
        "reports",
    ]
    domain_modules = {
        "support": ["ticket_inbox", "ticket_triage", "knowledge_base", "reply_drafts", "escalations"],
        "crm": ["contacts", "leads", "pipeline", "activities", "follow_ups"],
        "booking": ["calendar", "availability", "appointments", "reminders", "customer_records"],
        "commerce": ["catalog", "cart", "orders", "payments", "invoices"],
        "operations": ["work_items", "workflow_states", "approvals", "documents", "metrics"],
        "learning": ["courses", "lessons", "enrollments", "progress", "assessments"],
        "content": ["content_items", "editorial_workflow", "publishing", "categories", "search"],
        "custom_software": ["core_records", "business_workflows", "search", "exports"],
    }

    return {
        "project_name": project_name,
        "goal": goal,
        "domain": domain,
        "stack": stack,
        "product_principles": [
            "Build the actual usable product first, not a marketing landing page.",
            "Keep workflows simple enough for a small business owner to operate.",
            "Prefer local/open-source dependencies unless the CEO explicitly approves paid services.",
            "Every important action should be reviewable, logged, and reversible where practical.",
        ],
        "expected_modules": [*common_modules, *domain_modules.get(domain, domain_modules["custom_software"])],
        "data_model_guidance": [
            "Separate persistence models from API request/response schemas.",
            "Name entities after the business domain, not generic placeholders.",
            "Include created/updated timestamps on important records.",
            "Avoid storing secrets, passwords, or external credentials in source code.",
        ],
        "automation_opportunities": [
            "Generate reports from stored operational data.",
            "Create tasks/escalations when records cannot be resolved automatically.",
            "Queue external communication for CEO approval before sending.",
            "Use deterministic checks before relying on AI-generated decisions.",
        ],
        "release_gates": [
            "Build/test passes.",
            "Quality review has no blocking findings.",
            "Security review has no high-risk findings.",
            "Open approvals and support escalations are resolved or explicitly accepted by the CEO.",
        ],
    }


def write_blueprint(project_dir: str, blueprint: dict, overwrite: bool = False) -> dict:
    root = Path(project_dir).resolve()
    json_path = safe_project_path(root, BLUEPRINT_JSON)
    md_path = safe_project_path(root, BLUEPRINT_MD)
    json_path.parent.mkdir(parents=True, exist_ok=True)

    if overwrite or not json_path.exists():
        json_path.write_text(json.dumps(blueprint, indent=2), encoding="utf-8")
    if overwrite or not md_path.exists():
        md_path.write_text(format_blueprint_markdown(blueprint), encoding="utf-8")

    return {
        "blueprint_json": str(json_path),
        "blueprint_markdown": str(md_path),
    }


def ensure_blueprint(project_dir: str, project_name: str, goal: str, stack: str, overwrite: bool = False) -> dict:
    blueprint = blueprint_for(project_name, goal, stack)
    paths = write_blueprint(project_dir, blueprint, overwrite=overwrite)
    return {
        "blueprint": blueprint,
        "paths": paths,
    }


def ensure_project_blueprint(project_id: int, overwrite: bool = False) -> dict | None:
    db = SessionLocal()
    try:
        project = db.query(Project).filter(Project.id == project_id).first()
        if project is None:
            return None
        project_dir = project.project_path or str(resolve_output_dir(project.name))
        project_name = project.name
        goal = project.description or ""
    finally:
        db.close()

    stack = "unknown"
    architecture_path = Path(project_dir) / ".wacko" / "architecture.json"
    if architecture_path.exists():
        try:
            stack = json.loads(architecture_path.read_text(encoding="utf-8")).get("stack", "unknown")
        except json.JSONDecodeError:
            stack = "unknown"

    result = ensure_blueprint(project_dir, project_name, goal, stack, overwrite=overwrite)
    return {
        "project_id": project_id,
        "project_path": project_dir,
        **result,
    }


def format_blueprint_markdown(blueprint: dict) -> str:
    lines = [
        f"# {blueprint.get('project_name', 'Project')} System Blueprint",
        "",
        f"Domain: {blueprint.get('domain', 'custom_software')}",
        f"Stack: {blueprint.get('stack', 'unknown')}",
        "",
        "## Goal",
        blueprint.get("goal", ""),
        "",
        "## Product Principles",
    ]
    for item in blueprint.get("product_principles", []):
        lines.append(f"- {item}")

    lines.extend(["", "## Expected Modules"])
    for item in blueprint.get("expected_modules", []):
        lines.append(f"- {item}")

    lines.extend(["", "## Data Model Guidance"])
    for item in blueprint.get("data_model_guidance", []):
        lines.append(f"- {item}")

    lines.extend(["", "## Automation Opportunities"])
    for item in blueprint.get("automation_opportunities", []):
        lines.append(f"- {item}")

    lines.extend(["", "## Release Gates"])
    for item in blueprint.get("release_gates", []):
        lines.append(f"- {item}")

    return "\n".join(lines) + "\n"
