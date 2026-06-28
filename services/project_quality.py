import ast
from pathlib import Path

from services.project_file_service import project_root_for


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def audit_python_project(project_id: int) -> dict | None:
    root = project_root_for(project_id)
    if root is None:
        return None

    findings = []
    if not (root / ".wacko" / "architecture.json").exists() or not (root / "ARCHITECTURE.md").exists():
        findings.append({
            "severity": "MEDIUM",
            "file": "ARCHITECTURE.md",
            "message": "Project has no architecture contract. Generate one before allowing multiple agents to edit shared files.",
        })

    files = sorted([*root.glob("app/*.py"), *root.glob("backend/app/*.py")])
    for path in files:
        relative = str(path.relative_to(root)).replace("\\", "/")
        try:
            content = _read(path)
        except OSError as exc:
            findings.append({
                "severity": "HIGH",
                "file": relative,
                "message": f"Could not read file: {exc}",
            })
            continue

        try:
            tree = ast.parse(content, filename=relative)
        except SyntaxError as exc:
            findings.append({
                "severity": "CRITICAL",
                "file": relative,
                "message": f"Python syntax error: {exc.msg}",
            })
            continue

        imported = set()
        defined = set()
        used = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.asname or alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                imported.update(alias.asname or alias.name for alias in node.names)
            elif isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                defined.add(node.name)
            elif isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        defined.add(target.id)
            elif isinstance(node, ast.Name):
                used.add(node.id)

        known_problem_names = {"JSONB", "DateTime", "datetime", "BaseModel", "Base", "get_db", "DATABASE_URL"}
        missing = sorted(name for name in known_problem_names if name in used and name not in imported and name not in defined)
        if missing:
            findings.append({
                "severity": "HIGH",
                "file": relative,
                "message": f"Uses names that are not imported or defined: {', '.join(missing)}",
            })

        if "dict[str, any]" in content:
            findings.append({
                "severity": "MEDIUM",
                "file": relative,
                "message": "Uses dict[str, any]; use typing.Any instead of the any() builtin.",
            })

    models = next((path for path in [root / "app/models.py", root / "backend/app/models.py"] if path.exists()), None)
    routes = next((path for path in [root / "app/routes.py", root / "backend/app/routes.py"] if path.exists()), None)
    database = next((path for path in [root / "app/database.py", root / "backend/app/database.py"] if path.exists()), None)
    email_service = next((path for path in [root / "app/email_service.py", root / "backend/app/email_service.py"] if path.exists()), None)

    models_text = _read(models) if models else ""
    routes_text = _read(routes) if routes else ""
    database_text = _read(database) if database else ""
    email_text = _read(email_service) if email_service else ""

    if routes and "get_db" in routes_text and database and "def get_db" not in database_text:
        findings.append({
            "severity": "HIGH",
            "file": str(routes.relative_to(root)).replace("\\", "/"),
            "message": "Routes import/use get_db, but database.py does not define get_db().",
        })

    if models and routes and "class Ticket(Base)" in models_text and "db.add(ticket)" in routes_text:
        findings.append({
            "severity": "CRITICAL",
            "file": str(models.relative_to(root)).replace("\\", "/"),
            "message": "Ticket appears to be used as both ORM model and API schema. Split ORM models from Pydantic schemas.",
        })

    if email_service and "notification.to" in email_text and models:
        email_class_start = models_text.find("class EmailNotification")
        email_class = models_text[email_class_start:] if email_class_start != -1 else ""
        email_class = email_class.split("\nclass ", 1)[0]
        if "to:" not in email_class:
            findings.append({
                "severity": "HIGH",
                "file": str(email_service.relative_to(root)).replace("\\", "/"),
                "message": "email_service.py uses notification.to, but EmailNotification has no to field.",
            })

    severity_order = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}
    findings.sort(key=lambda item: (severity_order.get(item["severity"], 9), item["file"]))
    status = "PASS" if not findings else "FAIL"
    return {
        "project_id": project_id,
        "project_path": str(root),
        "status": status,
        "findings": findings,
    }
