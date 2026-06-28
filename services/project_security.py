import re
from pathlib import Path

from services.project_file_service import is_text_file, project_root_for
from services.project_reader import SKIP_DIRS


SECRET_PATTERNS = [
    ("HIGH", "Possible private key", re.compile(r"-----BEGIN (?:RSA |OPENSSH |EC |DSA )?PRIVATE KEY-----")),
    ("HIGH", "Hardcoded password assignment", re.compile(r"(?i)(password|passwd|pwd)\s*=\s*['\"][^'\"\n]{4,}['\"]")),
    ("HIGH", "Hardcoded API key/token", re.compile(r"(?i)(api[_-]?key|secret|token)\s*=\s*['\"][^'\"\n]{12,}['\"]")),
    ("MEDIUM", "Placeholder SMTP credential", re.compile(r"(?i)(smtp_password|smtp_username|your-password|your-email@example\.com)")),
]

DEPENDENCY_WARNINGS = {
    "httpx2": "Suspicious dependency. Verify this is intentional and not a hallucinated fix for httpx/testclient.",
    "psycopg2-binary": "PostgreSQL dependency present. Ensure the project actually uses PostgreSQL.",
}


def scan_project_security(project_id: int) -> dict | None:
    root = project_root_for(project_id)
    if root is None:
        return None

    findings = []
    if not root.exists():
        return {
            "project_id": project_id,
            "project_path": str(root),
            "status": "FAIL",
            "findings": [{
                "severity": "HIGH",
                "file": "",
                "message": "Project path does not exist.",
            }],
        }

    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(root)
        parts = set(relative.parts)
        if parts & SKIP_DIRS:
            continue
        if path.stat().st_size > 500_000 or not is_text_file(path):
            continue

        rel = str(relative).replace("\\", "/")
        try:
            content = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue

        for severity, label, pattern in SECRET_PATTERNS:
            if pattern.search(content):
                findings.append({
                    "severity": severity,
                    "file": rel,
                    "message": label,
                })

        lowered = content.lower()
        if rel.endswith(("main.py", "app.py")) and "allow_origins=[\"*\"]" in lowered:
            findings.append({
                "severity": "MEDIUM",
                "file": rel,
                "message": "CORS allows all origins. Lock this down before exposing outside localhost.",
            })
        if rel.endswith("email_service.py") and "smtplib.smtp" in lowered and "os.getenv" not in lowered:
            findings.append({
                "severity": "HIGH",
                "file": rel,
                "message": "SMTP service appears to use hardcoded settings instead of environment variables.",
            })
        if rel.endswith((".env", ".env.local")):
            findings.append({
                "severity": "HIGH",
                "file": rel,
                "message": "Environment file should not be committed or generated with real secrets.",
            })

        if Path(rel).name.lower() in {"requirements.txt", "pyproject.toml", "package.json"}:
            for dep, warning in DEPENDENCY_WARNINGS.items():
                if dep in lowered:
                    findings.append({
                        "severity": "MEDIUM",
                        "file": rel,
                        "message": warning,
                    })

    severity_order = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}
    findings.sort(key=lambda item: (severity_order.get(item["severity"], 9), item["file"], item["message"]))
    return {
        "project_id": project_id,
        "project_path": str(root),
        "status": "PASS" if not findings else "WARN",
        "findings": findings,
    }
