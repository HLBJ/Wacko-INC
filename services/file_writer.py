import os
import json
import re
from pathlib import Path


DEFAULT_OUTPUT_BASE = "C:/Project"


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
      3. C:/Project/<slugified project name>
    """
    if output_dir:
        return Path(output_dir)

    base = os.getenv("OUTPUT_BASE_DIR", DEFAULT_OUTPUT_BASE)
    return Path(base) / slugify(project_name)


def safe_project_path(base: Path, relative_path: str) -> Path:
    clean_path = relative_path.strip().strip("\"'")
    if not clean_path:
        raise ValueError("Generated file path cannot be empty.")

    candidate = (base / clean_path).resolve()
    resolved_base = base.resolve()
    if candidate != resolved_base and resolved_base not in candidate.parents:
        raise ValueError(f"Generated file path escapes project directory: {relative_path}")
    return candidate


def is_placeholder_path(relative_path: str) -> bool:
    normalized = relative_path.strip().replace("\\", "/").lower()
    placeholders = {
        "relative/path/from/project/root.ext",
        "path/to/file.ext",
        "relative/path/file.ext",
        "filename.ext",
    }
    return normalized in placeholders or normalized.startswith("relative/path/from/project/")


def extract_generated_files(output: str) -> list[tuple[str, str]]:
    files = []
    stripped = output.strip()

    json_candidates = [stripped]
    first = stripped.find("{")
    last = stripped.rfind("}")
    if first != -1 and last != -1 and first < last:
        json_candidates.append(stripped[first:last + 1])

    for candidate in json_candidates:
        try:
            payload = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if not isinstance(payload, dict) or not isinstance(payload.get("files"), list):
            continue
        for item in payload["files"]:
            if not isinstance(item, dict):
                continue
            relative_path = str(item.get("path", "")).strip()
            content = item.get("content")
            if relative_path and isinstance(content, str):
                files.append((relative_path, content if content.endswith("\n") else content + "\n"))
        if files:
            return files

    file_block_pattern = re.compile(
        r"```file(?:\s+path=)?[\"']?([^\"'\n`]+)[\"']?\s*\n(.*?)```",
        re.IGNORECASE | re.DOTALL,
    )
    for match in file_block_pattern.finditer(output):
        files.append((match.group(1).strip(), match.group(2).strip() + "\n"))

    heading_pattern = re.compile(
        r"^#{2,6}\s*File:\s*(.+?)\s*\r?\n```[^\n]*\r?\n(.*?)```",
        re.IGNORECASE | re.MULTILINE | re.DOTALL,
    )
    for match in heading_pattern.finditer(output):
        files.append((match.group(1).strip(), match.group(2).strip() + "\n"))

    return files


def write_agent_output(
    project_name: str,
    task_title: str,
    agent_name: str,
    output: str,
    output_dir: str | None = None,
) -> dict:
    """
    Write an agent's output to disk and return the file path.

    Layout:
        <project_dir>/
            .wacko/
                agent_notes/
                    <agent_name>/
                        <safe_task_title>.md
            generated files from agent-provided file blocks
    """
    base = resolve_output_dir(project_name, output_dir)
    agent_dir = base / ".wacko" / "agent_notes" / slugify(agent_name)
    agent_dir.mkdir(parents=True, exist_ok=True)

    filename = slugify(task_title) + ".md"
    note_path = agent_dir / filename

    header = f"# {task_title}\n\n**Agent:** {agent_name}  \n**Project:** {project_name}\n\n---\n\n"
    note_path.write_text(header + output, encoding="utf-8")

    generated_paths = []
    for relative_path, content in extract_generated_files(output):
        if is_placeholder_path(relative_path):
            continue
        file_path = safe_project_path(base, relative_path)
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(content, encoding="utf-8")
        generated_paths.append(str(file_path))

    return {
        "project_dir": str(base),
        "note_file": str(note_path),
        "generated_files": generated_paths,
    }
