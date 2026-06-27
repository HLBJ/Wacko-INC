import os
import re
from pathlib import Path


DEFAULT_OUTPUT_BASE = "C:/Projects"


def slugify(name: str) -> str:
    """Convert a project name to a safe directory name."""
    name = name.strip()
    name = re.sub(r"[^\w\s-]", "", name)
    name = re.sub(r"[\s_-]+", "_", name)
    return name.strip("_") or "Project"


def resolve_output_dir(project_name: str, output_dir: str | None = None) -> Path:
    """
    Return the resolved output directory for a project.

    Priority:
      1. Explicit output_dir passed by the caller (e.g. from the API payload)
      2. OUTPUT_BASE_DIR env var  +  slugified project name
      3. C:/Projects/<slugified project name>
    """
    if output_dir:
        return Path(output_dir)

    base = os.getenv("OUTPUT_BASE_DIR", DEFAULT_OUTPUT_BASE)
    return Path(base) / slugify(project_name)


def write_agent_output(
    project_name: str,
    task_title: str,
    agent_name: str,
    output: str,
    output_dir: str | None = None,
) -> Path:
    """
    Write an agent's output to disk and return the file path.

    Layout:
        <output_dir>/
            <agent_name>/
                <safe_task_title>.md
    """
    base = resolve_output_dir(project_name, output_dir)
    agent_dir = base / slugify(agent_name)
    agent_dir.mkdir(parents=True, exist_ok=True)

    filename = slugify(task_title) + ".md"
    file_path = agent_dir / filename

    header = f"# {task_title}\n\n**Agent:** {agent_name}  \n**Project:** {project_name}\n\n---\n\n"
    file_path.write_text(header + output, encoding="utf-8")

    return file_path
