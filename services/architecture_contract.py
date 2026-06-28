import json
from pathlib import Path

from database.db import SessionLocal
from database.models import Project
from services.file_writer import resolve_output_dir, safe_project_path


CONTRACT_JSON = ".wacko/architecture.json"
CONTRACT_MD = "ARCHITECTURE.md"


def contract_for_stack(project_name: str, stack: str, goal: str = "") -> dict:
    common = {
        "project_name": project_name,
        "stack": stack,
        "goal": goal,
        "rules": [
            "Preserve working code unless a task explicitly requires replacing it.",
            "Keep implementation changes small, reviewable, and tied to the task.",
            "When changing a shared file, update all dependent imports and tests in the same response.",
            "Agents must read project memory and recent handoffs before editing files.",
        ],
        "ownership": {
            "manager": ["ARCHITECTURE.md", ".wacko/project_memory.md", "README.md"],
            "security": ["security notes", "configuration review", "dependency and secrets findings"],
            "testing": ["tests/**", "test configuration", "test fixtures"],
        },
        "forbidden_patterns": [
            "Do not use one class as both persistence model and API request/response schema when the framework expects separate layers.",
            "Do not hard-code production secrets or credentials.",
            "Do not add fake dependencies to silence errors without verifying the root cause.",
        ],
    }

    if stack == "fastapi":
        common["layers"] = {
            "api": "app/main.py and app/routes.py expose HTTP endpoints.",
            "schemas": "app/schemas.py contains Pydantic request and response models.",
            "persistence": "app/models.py contains SQLAlchemy ORM models only.",
            "database": "app/database.py owns engine/session/get_db setup.",
            "services": "app/*_service.py contains business integrations such as email.",
            "tests": "tests/ contains deterministic tests that do not require external paid services.",
        }
        common["ownership"].update({
            "backend": ["app/main.py", "app/routes.py", "app/schemas.py", "app/*_service.py", "tests/**"],
            "database": ["app/database.py", "app/models.py", "migrations/**"],
            "frontend": ["static/**", "templates/**", "frontend/**", "src/**"],
        })
    elif stack == "fastapi-vue":
        common["layers"] = {
            "backend_api": "backend/app/main.py and backend/app/routes.py expose HTTP endpoints.",
            "backend_schemas": "backend/app/schemas.py contains Pydantic request and response models.",
            "backend_persistence": "backend/app/models.py contains SQLAlchemy ORM models only.",
            "backend_database": "backend/app/database.py owns engine/session/get_db setup.",
            "frontend": "frontend/src contains Vue UI components and client code.",
            "tests": "backend/tests and frontend tests contain deterministic checks.",
        }
        common["ownership"].update({
            "backend": ["backend/app/main.py", "backend/app/routes.py", "backend/app/schemas.py", "backend/app/*_service.py", "backend/tests/**"],
            "database": ["backend/app/database.py", "backend/app/models.py", "backend/migrations/**"],
            "frontend": ["frontend/**"],
        })
    elif stack == "vue":
        common["layers"] = {
            "frontend": "src contains Vue UI components, state, routes, and client services.",
            "build": "package.json and Vite config own frontend build behavior.",
            "tests": "frontend tests should cover user-visible behavior.",
        }
        common["ownership"].update({
            "frontend": ["src/**", "index.html", "package.json", "vite.config.*"],
            "backend": ["api client stubs only when required"],
            "database": ["no database ownership unless project adds a backend"],
        })
    elif stack == "dotnet-api":
        common["layers"] = {
            "api": "src/Program.cs and controllers/endpoints expose HTTP behavior.",
            "domain": "domain models and services own business logic.",
            "persistence": "EF Core DbContext and migrations own database behavior.",
            "tests": "test projects verify API and domain behavior.",
        }
        common["ownership"].update({
            "backend": ["src/**", "tests/**"],
            "database": ["DbContext", "migrations/**", "entity configurations"],
            "frontend": ["no frontend ownership unless project adds a UI"],
        })
    else:
        common["layers"] = {
            "application": "Follow the existing project structure and document any new layers.",
        }
        common["ownership"].update({
            "backend": ["backend/API/service files"],
            "database": ["schema/database files"],
            "frontend": ["UI/client files"],
        })

    return common


def detect_stack_from_path(project_dir: str) -> str:
    root = Path(project_dir)
    if (root / "backend" / "requirements.txt").exists() and (root / "frontend" / "package.json").exists():
        return "fastapi-vue"
    if (root / "requirements.txt").exists() or (root / "app" / "main.py").exists():
        return "fastapi"
    if (root / "package.json").exists():
        return "vue"
    if any(root.rglob("*.csproj")) or (root / "src" / "Program.cs").exists():
        return "dotnet-api"
    return "unknown"


def contract_paths(project_dir: str) -> tuple[Path, Path]:
    root = Path(project_dir).resolve()
    return safe_project_path(root, CONTRACT_JSON), safe_project_path(root, CONTRACT_MD)


def write_contract(project_dir: str, contract: dict, overwrite: bool = False) -> dict:
    json_path, md_path = contract_paths(project_dir)
    json_path.parent.mkdir(parents=True, exist_ok=True)

    if overwrite or not json_path.exists():
        json_path.write_text(json.dumps(contract, indent=2), encoding="utf-8")

    if overwrite or not md_path.exists():
        md_path.write_text(format_contract_markdown(contract), encoding="utf-8")

    return {
        "architecture_json": str(json_path),
        "architecture_markdown": str(md_path),
    }


def ensure_contract(project_dir: str, project_name: str, stack: str = "unknown", goal: str = "") -> dict:
    json_path, _ = contract_paths(project_dir)
    if json_path.exists():
        try:
            return json.loads(json_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pass

    contract = contract_for_stack(project_name, stack, goal)
    write_contract(project_dir, contract)
    return contract


def read_contract_text(project_dir: str, project_name: str, stack: str = "unknown") -> str:
    contract = ensure_contract(project_dir, project_name, stack)
    return json.dumps(contract, indent=2)


def ensure_project_contract(project_id: int, overwrite: bool = False) -> dict | None:
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

    stack = detect_stack_from_path(project_dir)
    contract = contract_for_stack(project_name, stack, goal)
    paths = write_contract(project_dir, contract, overwrite=overwrite)
    return {
        "project_id": project_id,
        "project_path": project_dir,
        "stack": stack,
        "contract": contract,
        "paths": paths,
    }


def format_contract_markdown(contract: dict) -> str:
    lines = [
        f"# {contract.get('project_name', 'Project')} Architecture",
        "",
        f"Stack: {contract.get('stack', 'unknown')}",
        "",
        "## Layers",
    ]
    for name, description in contract.get("layers", {}).items():
        lines.append(f"- **{name}:** {description}")

    lines.extend(["", "## Ownership"])
    for role, paths in contract.get("ownership", {}).items():
        lines.append(f"- **{role}:** {', '.join(paths)}")

    lines.extend(["", "## Rules"])
    for rule in contract.get("rules", []):
        lines.append(f"- {rule}")

    lines.extend(["", "## Forbidden Patterns"])
    for pattern in contract.get("forbidden_patterns", []):
        lines.append(f"- {pattern}")

    return "\n".join(lines) + "\n"
