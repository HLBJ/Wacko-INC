import json
import re
from pathlib import Path

from llm import model_for, run_model
from services.architecture_contract import contract_for_stack, detect_stack_from_path, write_contract
from services.orchestrator import run_task
from services.project_service import ProjectService
from services.project_reader import format_project_context, read_project_context
from services.project_templates import seed_project_template, template_for
from services.roadmap_service import ensure_project_roadmap
from services.system_blueprint import infer_domain
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


DOMAIN_TASKS = {
    "crm": [
        {
            "title": "Design CRM contact and lead workflows",
            "description": "Define contacts, leads, pipeline stages, activities, follow-ups, and reporting needs.",
            "assigned_agent": "manager",
            "priority": "HIGH",
        },
        {
            "title": "Build CRM backend data model and API",
            "description": "Create the backend entities, API endpoints, validation, and service boundaries for CRM workflows.",
            "assigned_agent": "backend",
            "priority": "HIGH",
        },
        {
            "title": "Design CRM user interface",
            "description": "Create screens for contacts, leads, pipeline boards, activity history, and dashboard metrics.",
            "assigned_agent": "frontend",
            "priority": "HIGH",
        },
    ],
    "booking": [
        {
            "title": "Design booking and availability rules",
            "description": "Define calendars, time slots, availability, appointment statuses, reminders, and cancellation rules.",
            "assigned_agent": "manager",
            "priority": "HIGH",
        },
        {
            "title": "Build booking backend and API",
            "description": "Create appointment, customer, availability, and reminder endpoints with validation.",
            "assigned_agent": "backend",
            "priority": "HIGH",
        },
        {
            "title": "Design booking user experience",
            "description": "Create customer booking flow, staff calendar views, and appointment management screens.",
            "assigned_agent": "frontend",
            "priority": "HIGH",
        },
    ],
    "commerce": [
        {
            "title": "Design commerce workflows",
            "description": "Define catalog, cart, checkout, orders, payments, invoices, and fulfilment workflows.",
            "assigned_agent": "manager",
            "priority": "HIGH",
        },
        {
            "title": "Build commerce backend and data model",
            "description": "Create product, customer, order, payment status, and invoice structures and APIs.",
            "assigned_agent": "backend",
            "priority": "HIGH",
        },
        {
            "title": "Design commerce storefront and admin UI",
            "description": "Create catalog browsing, checkout, order history, and product management screens.",
            "assigned_agent": "frontend",
            "priority": "HIGH",
        },
    ],
    "support": [
        {
            "title": "Design support operations workflow",
            "description": "Define tickets, categories, assignment, reply drafts, escalation rules, and knowledge base behavior.",
            "assigned_agent": "manager",
            "priority": "HIGH",
        },
        {
            "title": "Build support backend and ticket APIs",
            "description": "Create ticket, reply, knowledge article, notification, and escalation endpoints.",
            "assigned_agent": "backend",
            "priority": "HIGH",
        },
        {
            "title": "Design support inbox UI",
            "description": "Create ticket list, ticket detail, reply draft, knowledge search, and escalation screens.",
            "assigned_agent": "frontend",
            "priority": "HIGH",
        },
    ],
}


def fallback_tasks_for_goal(goal: str) -> list[dict]:
    domain = infer_domain(goal)
    tasks = [*DOMAIN_TASKS.get(domain, DEFAULT_TASKS[:3])]
    tasks.extend(DEFAULT_TASKS[3:])
    seen = set()
    unique = []
    for task in tasks:
        if task["title"] in seen:
            continue
        seen.add(task["title"])
        unique.append(task)
    return unique


def submit_company_goal(
    goal: str,
    auto_start: bool = True,
    output_dir: str | None = None,
    stack: str = "auto",
) -> dict:
    plan = create_manager_plan(goal, stack)
    template_result = seed_project_template(plan["project_name"], goal, stack, output_dir)
    project = ProjectService.create_project(
        plan["project_name"],
        plan["project_description"],
        project_path=template_result["project_dir"],
    )
    ensure_project_roadmap(project.id)

    planning_task = TaskService.create_task(
        project.id,
        "Manager project plan",
        f"{plan['manager_summary']}\n\nTemplate:\n{json.dumps(template_result, indent=2)}",
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
        description = (
            f"{task_data['description']}\n\n"
            f"Project directory:\n{template_result['project_dir']}\n\n"
            f"Selected stack/template:\n{template_result['template_name']} ({template_result['stack']})\n\n"
            "Update or create files in this project. Keep paths relative to the project root."
        )
        task = TaskService.create_task(
            project.id,
            task_data["title"],
            description,
            assigned_agent=task_data["assigned_agent"],
            priority=task_data.get("priority", "MEDIUM"),
            requires_approval=True,
        )
        created_tasks.append(task)

    if auto_start:
        run_project_tasks(project.id, skip_task_ids={planning_task.id}, output_dir=output_dir)

    return {
        "project": project,
        "planning_task": planning_task,
        "tasks": created_tasks,
        "template": template_result,
        "auto_started": auto_start,
    }


def submit_project_update(
    project_path: str,
    instructions: str,
    auto_start: bool = True,
) -> dict:
    context = read_project_context(project_path)
    plan = create_update_plan(instructions, context)

    project = ProjectService.create_project(
        plan["project_name"],
        f"Update existing project at {context['root']}. {plan['project_description']}",
        project_path=context["root"],
    )
    detected_stack = detect_stack_from_path(context["root"])
    write_contract(
        context["root"],
        contract_for_stack(plan["project_name"], detected_stack, instructions),
    )

    planning_task = TaskService.create_task(
        project.id,
        "Manager update plan",
        plan["manager_summary"],
        assigned_agent="manager",
        priority="HIGH",
        requires_approval=True,
    )

    planning_run = TaskService.create_run(planning_task.id, "manager", instructions)
    TaskService.complete_run(planning_run.id, json.dumps(plan, indent=2), "COMPLETED")
    TaskService.update_status(planning_task.id, "AWAITING_APPROVAL")
    TaskService.create_approval(
        planning_task.id,
        "Approve manager update plan",
        "Review the Manager's generated update plan before treating the plan as accepted.",
    )

    created_tasks = []
    project_context = format_project_context(context)
    for task_data in plan["tasks"]:
        description = (
            f"{task_data['description']}\n\n"
            f"CEO update request:\n{instructions}\n\n"
            "Existing project context:\n"
            f"{project_context}\n\n"
            "Write updated project files. Only include files that should be created or changed."
        )
        task = TaskService.create_task(
            project.id,
            task_data["title"],
            description,
            assigned_agent=task_data["assigned_agent"],
            priority=task_data.get("priority", "MEDIUM"),
            requires_approval=True,
        )
        created_tasks.append(task)

    if auto_start:
        run_project_tasks(project.id, skip_task_ids={planning_task.id}, output_dir=context["root"])

    return {
        "project": project,
        "planning_task": planning_task,
        "tasks": created_tasks,
        "project_path": context["root"],
        "auto_started": auto_start,
    }


def create_manager_plan(goal: str, stack: str = "auto") -> dict:
    template_key, template = template_for(stack)
    prompt = f"""
You are the Manager Agent for Wacko Inc, a local AI software development company.

The CEO gives you one goal. Your job is to create the project and delegate work to specialist agents.

CEO goal:
{goal}

Requested stack/template:
{template["name"]} ({template_key})

Template description:
{template["description"]}

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
- Implementation tasks must update the seeded project structure instead of inventing unrelated folders.
- Assign backend API, email, database, authentication, and third-party integration work to backend or database agents, not frontend.
- Assign frontend only when the task creates or changes actual UI/client files.
- Avoid multiple agents rewriting the same shared file unless the task says how their changes should fit together.
- Do not ask the CEO to manually create tasks.
"""

    output = run_model(model_for("manager", "qwen2.5:3b"), prompt)
    parsed = parse_json_plan(output)
    if parsed is None:
        return fallback_plan(goal, output)
    return normalize_plan(goal, parsed)


def create_update_plan(instructions: str, context: dict) -> dict:
    prompt = f"""
You are the Manager Agent for Wacko Inc.

The CEO wants the agents to study and update an existing project.

CEO update request:
{instructions}

Existing project:
{format_project_context(context)}

Return only valid JSON. Do not include markdown fences or commentary.

Schema:
{{
  "project_name": "{Path(context['root']).name}",
  "project_description": "one paragraph",
  "manager_summary": "what you understood and how the agents will update the project",
  "tasks": [
    {{
      "title": "task title",
      "description": "clear update task details and acceptance criteria",
      "assigned_agent": "manager|frontend|backend|database|security|testing|marketing|support",
      "priority": "HIGH|MEDIUM|LOW"
    }}
  ]
}}

Rules:
- Prefer update tasks over greenfield creation tasks.
- Assign implementation changes to frontend, backend, or database agents.
- Include testing and security review tasks when code changes are requested.
- Each implementation task must tell the agent to write changed files with relative paths.
- Do not ask the CEO to manually create tasks.
"""

    output = run_model(model_for("manager", "qwen2.5:3b"), prompt)
    parsed = parse_json_plan(output)
    if parsed is None:
        return normalize_plan(
            instructions,
            {
                "project_name": Path(context["root"]).name,
                "project_description": f"Update existing project at {context['root']}.",
                "manager_summary": "Created a fallback update plan because the Manager did not return structured JSON.",
                "tasks": [
                    {
                        "title": "Study existing project and implement requested changes",
                        "description": "Review the provided project context, then update the files needed for the CEO request.",
                        "assigned_agent": "backend",
                        "priority": "HIGH",
                    },
                    {
                        "title": "Review updated project quality and security",
                        "description": "Review the planned changes for correctness, security, and missing tests.",
                        "assigned_agent": "security",
                        "priority": "HIGH",
                    },
                    {
                        "title": "Create or update tests",
                        "description": "Create or update tests for the requested project changes.",
                        "assigned_agent": "testing",
                        "priority": "MEDIUM",
                    },
                ],
            },
        )
    return normalize_plan(instructions, parsed)


def parse_json_plan(output: str) -> dict | None:
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


def normalize_plan(goal: str, plan: dict) -> dict:
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


def fallback_plan(goal: str, manager_output: str) -> dict:
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
        "tasks": fallback_tasks_for_goal(goal),
    }


def run_project_tasks(
    project_id: int,
    skip_task_ids: set | None = None,
    output_dir: str | None = None,
) -> list[dict]:
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
        result = run_task(task.id, output_dir=output_dir)
        if result is not None:
            results.append(result)
    return results
