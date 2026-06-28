import subprocess
import sys
import shutil
from pathlib import Path


def resolve_executable(command: list[str]) -> list[str]:
    if not command:
        return command

    executable = command[0].lower()
    if executable in {"python", "python3"}:
        return [sys.executable, *command[1:]]

    found = shutil.which(command[0])
    if found:
        return [found, *command[1:]]

    dependencies_dir = Path(sys.executable).resolve().parents[1]
    candidates = {
        "node": dependencies_dir / "node" / "bin" / "node.exe",
        "npm": dependencies_dir / "node" / "bin" / "npm.cmd",
        "npx": dependencies_dir / "node" / "bin" / "npx.cmd",
    }
    candidate = candidates.get(executable)
    if candidate and candidate.exists():
        return [str(candidate), *command[1:]]

    return command


def run_command(command: list[str], cwd: str, timeout_seconds: int | None = None) -> dict:
    workdir = Path(cwd).resolve()
    resolved_command = resolve_executable(command)
    try:
        completed = subprocess.run(
            resolved_command,
            cwd=str(workdir),
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            shell=False,
        )
        output = (completed.stdout or "") + ("\n" + completed.stderr if completed.stderr else "")
        return {
            "command": " ".join(command),
            "resolved_command": " ".join(resolved_command),
            "exit_code": completed.returncode,
            "output": output.strip(),
            "timed_out": False,
        }
    except FileNotFoundError as exc:
        return {
            "command": " ".join(command),
            "resolved_command": " ".join(resolved_command),
            "exit_code": 127,
            "output": f"Command not found: {command[0]}\n{exc}",
            "timed_out": False,
        }
    except subprocess.TimeoutExpired as exc:
        output = (exc.stdout or "") + ("\n" + exc.stderr if exc.stderr else "")
        timeout_label = str(timeout_seconds) if timeout_seconds is not None else "no"
        return {
            "command": " ".join(command),
            "resolved_command": " ".join(resolved_command),
            "exit_code": 124,
            "output": f"Command timed out after {timeout_label} seconds.\n{output}".strip(),
            "timed_out": True,
        }
