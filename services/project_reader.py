from pathlib import Path


SKIP_DIRS = {
    ".git",
    ".wacko",
    "__pycache__",
    "bin",
    "build",
    "dist",
    "node_modules",
    "obj",
    "packages",
    ".venv",
    "venv",
}

TEXT_EXTENSIONS = {
    ".cs",
    ".css",
    ".env",
    ".html",
    ".java",
    ".js",
    ".json",
    ".md",
    ".py",
    ".sql",
    ".ts",
    ".tsx",
    ".txt",
    ".vue",
    ".xml",
    ".yaml",
    ".yml",
}


def score_path_for_task(relative_path: str, task_text: str) -> int:
    haystack = task_text.lower()
    path = relative_path.lower()
    filename = Path(path).name.lower()
    score = 0

    if filename in haystack:
        score += 8
    for part in Path(path).parts:
        if part.lower() in haystack:
            score += 3

    extension_weights = {
        ".vue": ["frontend", "ui", "screen", "component", "layout"],
        ".js": ["javascript", "frontend", "backend", "api"],
        ".ts": ["typescript", "frontend", "backend", "api"],
        ".py": ["python", "fastapi", "backend", "api"],
        ".cs": [".net", "asp.net", "backend", "api"],
        ".sql": ["database", "schema", "query", "migration"],
        ".html": ["frontend", "page", "ui", "layout"],
        ".css": ["style", "layout", "frontend", "ui"],
        ".json": ["config", "package", "settings"],
        ".md": ["readme", "documentation"],
    }
    for keyword in extension_weights.get(Path(path).suffix.lower(), []):
        if keyword in haystack:
            score += 2

    important_names = {"package.json", "requirements.txt", "pyproject.toml", "vite.config.js", "vite.config.ts", "README.md"}
    if filename in {name.lower() for name in important_names}:
        score += 2

    return score


def read_project_context(project_path: str, max_files: int = 35, max_chars_per_file: int = 5000) -> dict:
    root = Path(project_path).expanduser().resolve()
    if not root.exists() or not root.is_dir():
        raise ValueError(f"Project path does not exist or is not a directory: {project_path}")

    tree_lines = []
    file_summaries = []
    scanned = 0

    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root)
        parts = set(relative.parts)
        if parts & SKIP_DIRS:
            continue

        if path.is_dir():
            continue

        tree_lines.append(str(relative).replace("\\", "/"))
        if scanned >= max_files:
            continue
        if path.suffix.lower() not in TEXT_EXTENSIONS:
            continue
        if path.stat().st_size > 200_000:
            continue

        try:
            content = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue

        file_summaries.append({
            "path": str(relative).replace("\\", "/"),
            "content": content[:max_chars_per_file],
        })
        scanned += 1

    return {
        "root": str(root),
        "tree": tree_lines[:300],
        "files": file_summaries,
    }


def read_relevant_project_context(
    project_path: str,
    task_text: str,
    max_files: int = 18,
    max_chars_per_file: int = 3500,
) -> dict:
    context = read_project_context(project_path, max_files=120, max_chars_per_file=max_chars_per_file)
    scored_files = sorted(
        context["files"],
        key=lambda item: score_path_for_task(item["path"], task_text),
        reverse=True,
    )
    selected = [item for item in scored_files if score_path_for_task(item["path"], task_text) > 0]
    if len(selected) < min(max_files, 8):
        selected = scored_files

    return {
        "root": context["root"],
        "tree": context["tree"],
        "files": selected[:max_files],
    }


def format_project_context(context: dict) -> str:
    tree = "\n".join(f"- {path}" for path in context["tree"]) or "- No files found"
    files = []
    for item in context["files"]:
        files.append(
            f"### {item['path']}\n"
            "```text\n"
            f"{item['content']}\n"
            "```"
        )

    file_text = "\n\n".join(files) or "No readable source files found."
    return f"""
Project root:
{context["root"]}

File tree:
{tree}

Readable files:
{file_text}
"""
