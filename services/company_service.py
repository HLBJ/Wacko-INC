import json
import re

from llm import model_for, run_model
from services.orchestrator import run_task
from services.project_service import ProjectService
from services.task_service import TaskService


DEFAULT_TASKS = [
    {
        "title": "Create product brief and release scope",
        "description": "Define the target user, core value proposition, must-have features, and out-of-scope items.",
        "assigned_agent": "manager",
        "priority": "HIGH",
    },
    {
        "title": "Design frontend user experience",
        "description": "Create the main screens, user flows, layout requirements, and component plan.",
        "assigned_agent": "frontend",
        "priority": "HIGH",
    },
    {
        "title": "Design backend API and domain model",
        "description": "Define API endpoints, business logic, authentication needs, and service boundaries.",
        "assigned_agent": "backend",
        "priority": "HIGH",
    },
    {
        "title": "Design database schema",
        "description": "Define tables, relationships, indexes, and migration strategy.",
        "assigned_agent": "database",
        "priority": "MEDIUM",
    },
    {
        "title": "Review security and privacy risks",
        "description": "Identify authentication, authorization, secrets, dependency, and data privacy risks.",
        "assigned_agent": "security",
        "priority": "HIGH",
    },
    {
        "title": "Create test strategy",
        "description": "Plan unit, integration, UI, regression, and performance testing for the first release.",
        "assigned_agent": "testing",
        "priority": "MEDIUM",
    },
]


def submit_company_goal(goal, auto_start=True):
    plan = create_manager_plan(goal)
    project = ProjectService.create_project(plan["project_name"], plan["project_description"])

    planning_task = TaskService.create_task(
        project.id,
        "Manager project plan",
        plan["manager_summary"],
        assigned_agent="manager",
        priority="HIGH",
        requires_approval=True,
    )

    planning_run = TaskService.create_run(planning_task.id, "manager", goal)
    TaskService.complete_run(planning_run.id, json.dumps(plan, indent=2), "COMPLETED")
    TaskService.update_status(planning_task.id, "AWAITING_APPROVAL")
    TaskService.create_approval(
        planning_task.id,
        "Approve manager project plan",
        "Review the Manager's generated project breakdown before treating the plan as accepted.",
    )

    created_tasks = []
    for task_data in plan["tasks"]:
        task = TaskService.create_task(
            project.id,
            task_data["title"],
            task_data["description"],
            assigned_agent=task_data["assigned_agent"],
            priority=task_data.get("priority", "MEDIUM"),
            requires_approval=True,
        )
        created_tasks.append(task)

    if auto_start:
        run_project_tasks(project.id, skip_task_ids={planning_task.id})

    return {
        "project": project,
        "planning_task": planning_task,
        "tasks": created_tasks,
        "auto_started": auto_start,
    }


def create_manager_plan(goal):
    prompt = f"""
You are the Manager Agent for Wacko Inc, a local AI software development company.

The CEO gives you one goal. Your job is to create the project and delegate work to specialist agents.

CEO goal:
{goal}

Return only valid JSON. Do not include markdown fences or commentary.

Schema:
{{
  "project_name": "short project name",
  "project_description": "one paragraph",
  "manager_summary": "what you understood and how the company will execute",
  "tasks": [
    {{
      "title": "task title",
      "description": "clear task details and acceptance criteria",
      "assigned_agent": "manager|frontend|backend|database|security|testing|marketing|support",
      "priority": "HIGH|MEDIUM|LOW"
    }}
  ]
}}

Rules:
- Create enough tasks for a small team to execute the goal end to end.
- Assign each task to the best specialist agent.
- Include security and testing tasks for software projects.
- Include marketing/support tasks only when relevant.
- Do not ask the CEO to manually create tasks.
"""

    output = run_model(model_for("manager", "qwen2.5:3b"), prompt)
    parsed = parse_json_plan(output)
    if parsed is None:
        return fallback_plan(goal, output)
    return normalize_plan(goal, parsed)


def parse_json_plan(output):
    if output.startswith("LOCAL_MODEL_"):
        return None

    candidates = [output]
    fenced = re.findall(r"```(?:json)?\s*(.*?)```", output, flags=re.DOTALL | re.IGNORECASE)
    candidates.extend(fenced)

    object_match = re.search(r"\{.*\}", output, flags=re.DOTALL)
    if object_match:
        candidates.append(object_match.group(0))

    for candidate in candidates:
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            continue
    return None


def normalize_plan(goal, plan):
    tasks = plan.get("tasks") or []
    normalized_tasks = []
    valid_agents = {"manager", "frontend", "backend", "database", "security", "testing", "marketing", "support"}
    valid_priorities = {"HIGH", "MEDIUM", "LOW"}

    for task in tasks:
        title = str(task.get("title") or "Untitled task").strip()
        description = str(task.get("description") or "").strip()
        assigned_agent = str(task.get("assigned_agent") or "manager").strip().lower()
        priority = str(task.get("priority") or "MEDIUM").strip().upper()

        if assigned_agent not in valid_agents:
            assigned_agent = "manager"
        if priority not in valid_priorities:
            priority = "MEDIUM"

        normalized_tasks.append({
            "title": title,
            "description": description,
            "assigned_agent": assigned_agent,
            "priority": priority,
        })

    if not normalized_tasks:
        normalized_tasks = DEFAULT_TASKS

    return {
        "project_name": str(plan.get("project_name") or "AI Company Project").strip(),
        "project_description": str(plan.get("project_description") or goal).strip(),
        "manager_summary": str(plan.get("manager_summary") or "Manager generated an execution plan.").strip(),
        "tasks": normalized_tasks,
    }


def fallback_plan(goal, manager_output):
    summary = (
        "The Manager could not return a structured plan from the local model, "
        "so Wacko Inc created a standard software delivery workflow."
    )
    if manager_output:
        summary = f"{summary}\n\nManager output:\n{manager_output}"

    return {
        "project_name": goal.strip()[:80] or "AI Company Project",
        "project_description": goal,
        "manager_summary": summary,
        "tasks": DEFAULT_TASKS,
    }


def run_project_tasks(project_id, skip_task_ids=None):
    skip_task_ids = skip_task_ids or set()
    tasks = TaskService.list_tasks(project_id)
    runnable = [
        task for task in tasks
        if task.id not in skip_task_ids and task.status in {"BACKLOG", "NEEDS_CHANGES"}
    ]

    priority_order = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
    runnable.sort(key=lambda task: (priority_order.get(task.priority, 1), task.created_at))

    results = []
    for task in runnable:
        results.append(run_task(task.id))
    return results
