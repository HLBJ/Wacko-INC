import json
import os
import re
import ast
from pathlib import PurePosixPath
from typing import Any

from llm import model_for, ollama_health, run_model
from services.file_writer import is_placeholder_path


GATEWAY_PROVIDER = os.getenv("AI_GATEWAY_PROVIDER", "ollama")
JSON_CONTRACT = {
    "summary": "Short explanation of what was built or changed.",
    "files": [
        {
            "path": "relative/path/from/project/root.ext",
            "content": "complete file contents",
        }
    ],
    "commands": ["optional commands to install, build, or test"],
    "assumptions": ["important assumptions"],
    "risks": ["important risks or follow-up checks"],
}


class GatewayResponseError(ValueError):
    pass


def gateway_health() -> dict[str, Any]:
    health = ollama_health()
    return {
        "provider": GATEWAY_PROVIDER,
        "local_only": True,
        "ollama": health,
        "models": {
            "manager": model_for("manager", "qwen2.5:3b"),
            "developer": model_for("developer", "qwen2.5-coder:3b"),
            "reviewer": model_for("reviewer", "qwen2.5:3b"),
        },
        "contract": JSON_CONTRACT,
    }


def extract_json_object(text: str) -> dict[str, Any]:
    stripped = text.strip()
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", stripped, re.DOTALL | re.IGNORECASE)
    candidates = []
    if fenced:
        candidates.append(fenced.group(1))
    candidates.append(stripped)

    first = stripped.find("{")
    last = stripped.rfind("}")
    if first != -1 and last != -1 and first < last:
        candidates.append(stripped[first:last + 1])

    for candidate in candidates:
        try:
            parsed = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            return parsed

    raise GatewayResponseError("Model response did not contain a valid JSON object.")


def _validate_relative_path(path: str) -> None:
    normalized = path.strip().replace("\\", "/")
    pure_path = PurePosixPath(normalized)
    if not normalized:
        raise GatewayResponseError("Generated file path cannot be empty.")
    if normalized.startswith("/") or pure_path.is_absolute():
        raise GatewayResponseError(f"Generated file path must be relative: {path}")
    if any(part in ("", ".", "..") for part in pure_path.parts):
        raise GatewayResponseError(f"Generated file path contains an unsafe segment: {path}")
    if is_placeholder_path(normalized):
        raise GatewayResponseError(f"Generated file path is still a placeholder: {path}")


def normalize_file_change_payload(payload: dict[str, Any], require_files: bool = True) -> dict[str, Any]:
    files = payload.get("files")
    if not isinstance(files, list):
        raise GatewayResponseError("JSON contract requires a files array.")

    normalized_files = []
    for index, item in enumerate(files, start=1):
        if not isinstance(item, dict):
            raise GatewayResponseError(f"File entry {index} must be an object.")
        path = str(item.get("path", "")).strip()
        content = item.get("content")
        if not isinstance(content, str):
            raise GatewayResponseError(f"File entry {index} must include string content.")
        _validate_relative_path(path)
        _validate_file_content(path, content)
        normalized_files.append({"path": path.replace("\\", "/"), "content": content})

    if require_files and not normalized_files:
        raise GatewayResponseError("The response did not include any real project files.")

    _validate_payload_consistency(normalized_files)

    return {
        "summary": str(payload.get("summary", "")).strip(),
        "files": normalized_files,
        "commands": payload.get("commands") if isinstance(payload.get("commands"), list) else [],
        "assumptions": payload.get("assumptions") if isinstance(payload.get("assumptions"), list) else [],
        "risks": payload.get("risks") if isinstance(payload.get("risks"), list) else [],
    }


def _validate_payload_consistency(files: list[dict[str, str]]) -> None:
    by_path = {item["path"].replace("\\", "/").lower(): item["content"] for item in files}
    models = by_path.get("app/models.py") or by_path.get("backend/app/models.py") or ""
    routes = by_path.get("app/routes.py") or by_path.get("backend/app/routes.py") or ""
    database = by_path.get("app/database.py") or by_path.get("backend/app/database.py") or ""
    email_service = by_path.get("app/email_service.py") or by_path.get("backend/app/email_service.py") or ""

    if models and routes:
        ticket_is_orm = "class Ticket(Base)" in models or "class Ticket(Base," in models
        routes_uses_ticket_schema = "response_model=Ticket" in routes or "ticket: Ticket" in routes
        routes_persists_ticket_directly = "db.add(ticket)" in routes
        if ticket_is_orm and routes_uses_ticket_schema and routes_persists_ticket_directly:
            raise GatewayResponseError(
                "The response mixes one Ticket class as both SQLAlchemy ORM and FastAPI request/response schema. "
                "Separate ORM models from Pydantic schemas and update routes."
            )

    if routes and "get_db" in routes and database and "def get_db" not in database:
        raise GatewayResponseError("Routes import/use get_db, but the database file does not define def get_db().")

    if email_service and "notification.to" in email_service and models:
        email_notification_match = re.search(r"class\s+EmailNotification\b.*?(?:\nclass\s|\Z)", models, re.DOTALL)
        if email_notification_match and "to:" not in email_notification_match.group(0):
            raise GatewayResponseError("email_service.py uses notification.to, but EmailNotification has no to field.")


def _validate_file_content(path: str, content: str) -> None:
    normalized = path.replace("\\", "/").lower()
    if not normalized.endswith(".py"):
        return

    try:
        tree = ast.parse(content, filename=path)
    except SyntaxError as exc:
        raise GatewayResponseError(f"{path} has invalid Python syntax: {exc.msg}")

    imported_names = set()
    defined_names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imported_names.add(alias.asname or alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            for alias in node.names:
                imported_names.add(alias.asname or alias.name)
        elif isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            defined_names.add(node.name)
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    defined_names.add(target.id)

    available = imported_names | defined_names | set(dir(__builtins__))
    common_required = {"JSONB", "DateTime", "datetime", "BaseModel", "Base", "get_db", "DATABASE_URL"}
    used_names = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}
    missing = sorted(name for name in common_required if name in used_names and name not in available)
    if missing:
        raise GatewayResponseError(f"{path} uses names that are not imported or defined: {', '.join(missing)}")
    if "dict[str, any]" in content:
        raise GatewayResponseError(f"{path} uses dict[str, any]; use typing.Any instead of the any() builtin.")

    if normalized.endswith("routes.py") and "response_model=Ticket" in content:
        if "db.add(ticket)" in content and "class Ticket(Base)" in content:
            raise GatewayResponseError(
                f"{path} appears to use one Ticket class as both SQLAlchemy ORM and FastAPI response schema."
            )


def structured_file_change_prompt(role: str, task: str, feedback: str | None = None) -> str:
    contract = json.dumps(JSON_CONTRACT, indent=2)
    corrective_note = f"\nPrevious response problem: {feedback}\nTry again and fix only that problem.\n" if feedback else ""
    role_rules = {
        "frontend": (
            "- You are the Frontend Agent. Prefer UI files such as src/, frontend/, templates/, static/, or client-side components.\n"
            "- Do not rewrite backend API, database, or email-service files unless the task explicitly asks for frontend integration stubs.\n"
        ),
        "backend": (
            "- You are the Backend Agent. Own API routes, service modules, email handling, application wiring, and backend tests.\n"
            "- Keep persistence models, request schemas, and response schemas separated when the framework expects separate layers.\n"
        ),
        "database": (
            "- You are the Database Agent. Prefer schema, migration, repository, and database setup files.\n"
            "- Do not replace Pydantic/API schema files with ORM-only models unless you also update every import and route that depends on them.\n"
        ),
        "testing": (
            "- You are the Testing Agent. Prefer tests/, backend/tests/, fixtures, and test configuration files.\n"
            "- Write executable tests that verify real behavior and can run locally without paid external services.\n"
            "- Do not rewrite production code unless a tiny testability hook is required and clearly justified in risks.\n"
        ),
        "security": (
            "- You are the Security Agent. Fix secrets, hardcoded credentials, unsafe CORS, auth/privacy risks, and dependency hazards.\n"
            "- Prefer minimal security patches and configuration changes. Do not rewrite unrelated business logic.\n"
            "- Replace real or placeholder secrets with environment variables and update .env.example/README when needed.\n"
        ),
        "developer": (
            "- Preserve the existing architecture and update only files required for the task.\n"
        ),
    }.get(role, "- Preserve the existing architecture and update only files required for the task.\n")
    return f"""
You are the {role} in a local AI software company.

Implement the requested software task by returning only valid JSON. Do not use Markdown.

The JSON must match this contract:
{contract}

Hard rules:
- The files array must contain every source file needed for the implementation.
- Every file path must be relative to the project root.
- Never use placeholder paths such as relative/path/from/project/root.ext.
- File contents must be complete, not snippets.
- If the task is a change to an existing project, update the relevant files directly.
- Preserve existing working code unless the task requires replacing it.
- If changing a shared file, update all dependent imports/usages in the same response.
- Keep commands local and open-source only.
Role-specific rules:
{role_rules}
{corrective_note}
Task:
{task}
""".strip()


def generate_file_change_response(role: str, task: str, model: str | None = None, max_attempts: int = 3) -> str:
    selected_model = model or model_for(role, "qwen2.5-coder:3b")
    feedback = None
    last_response = ""

    for _ in range(max_attempts):
        prompt = structured_file_change_prompt(role, task, feedback)
        last_response = run_model(selected_model, prompt)
        if last_response.startswith(("LOCAL_MODEL_UNAVAILABLE", "LOCAL_MODEL_TIMEOUT")):
            return last_response
        try:
            payload = normalize_file_change_payload(extract_json_object(last_response), require_files=True)
            return json.dumps(payload, indent=2)
        except GatewayResponseError as exc:
            feedback = str(exc)

    fallback = {
        "summary": "The local model did not return valid file changes after retries.",
        "files": [],
        "commands": [],
        "assumptions": [],
        "risks": [feedback or "Unknown structured output error."],
        "raw_response": last_response,
    }
    return json.dumps(fallback, indent=2)
