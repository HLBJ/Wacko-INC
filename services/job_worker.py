import json
import os
import sys
import traceback

from database.schema import ensure_schema
from services.autopilot_service import run_project_autopilot
from services.build_service import run_project_build
from services.company_service import run_project_tasks
from services.job_event_service import record_job_event
from services.job_service import get_job, job_payload, mark_completed, mark_failed, mark_running, set_process_id, should_cancel
from services.orchestrator import run_task


DEFAULT_MAX_FIX_ATTEMPTS = 3


def serialize_result(result) -> str:
    try:
        return json.dumps(result, indent=2, default=str)
    except TypeError:
        return str(result)


def run_build_with_repairs(job, payload: dict) -> dict | None:
    max_fix_attempts = int(payload.get("max_fix_attempts", DEFAULT_MAX_FIX_ATTEMPTS) or DEFAULT_MAX_FIX_ATTEMPTS)
    auto_fix = bool(payload.get("auto_fix", True))
    attempts = []
    record_job_event(job.id, job.project_id, "Starting build/test run.")

    build_result = run_project_build(
        job.project_id,
        project_path=payload.get("project_path"),
        stack=payload.get("stack"),
    )
    attempts.append({"type": "build", "attempt": 0, "result": build_result})
    record_job_event(
        job.id,
        job.project_id,
        f"Build attempt 0 finished with {build_result.get('status') if build_result else 'UNKNOWN'}.",
        data={"result": build_result},
    )

    if not auto_fix:
        return {"status": build_result.get("status") if build_result else "UNKNOWN", "attempts": attempts}

    current = build_result
    for attempt_number in range(1, max_fix_attempts + 1):
        if not current or current.get("status") != "FAILED" or not current.get("fix_task_id"):
            break

        fix_result = run_task(current["fix_task_id"], output_dir=current.get("project_path"))
        attempts.append({"type": "fix", "attempt": attempt_number, "result": fix_result})
        record_job_event(
            job.id,
            job.project_id,
            f"Repair attempt {attempt_number} completed.",
            data={"fix_task_id": current["fix_task_id"], "result": fix_result},
        )

        current = run_project_build(
            job.project_id,
            project_path=current.get("project_path"),
            stack=current.get("stack"),
            create_fix_task=attempt_number < max_fix_attempts,
        )
        attempts.append({"type": "build", "attempt": attempt_number, "result": current})
        record_job_event(
            job.id,
            job.project_id,
            f"Build attempt {attempt_number} finished with {current.get('status') if current else 'UNKNOWN'}.",
            data={"result": current},
        )

        if current and current.get("status") == "PASSED":
            break

    return {
        "status": current.get("status") if current else "UNKNOWN",
        "max_fix_attempts": max_fix_attempts,
        "fix_attempts_used": len([item for item in attempts if item["type"] == "fix"]),
        "attempts": attempts,
    }


def run_job(job_id: int):
    ensure_schema()
    set_process_id(job_id, os.getpid())
    running = mark_running(job_id)
    if running is None or should_cancel(job_id):
        return

    job = get_job(job_id)
    if job is None:
        return
    payload = job_payload(job)
    record_job_event(job.id, job.project_id, f"Job started: {job.title or job.job_type}.", data={"job_type": job.job_type})

    if job.job_type in {"agent_project_run", "agent_project_update"}:
        result = run_project_tasks(
            job.project_id,
            skip_task_ids=set(payload.get("skip_task_ids", [])),
            output_dir=payload.get("output_dir"),
        )
        record_job_event(job.id, job.project_id, "Agent project run completed.", data={"result_count": len(result or [])})
    elif job.job_type == "full_cycle":
        agent_results = run_project_tasks(
            job.project_id,
            skip_task_ids=set(payload.get("skip_task_ids", [])),
            output_dir=payload.get("output_dir"),
        )
        if should_cancel(job_id):
            return
        build_result = run_build_with_repairs(job, payload)
        result = {
            "agent_results": agent_results,
            "build_result": build_result,
        }
        record_job_event(job.id, job.project_id, "Full cycle completed.", data={"build_status": (build_result or {}).get("status")})
    elif job.job_type == "agent_task_run":
        result = run_task(job.task_id, output_dir=payload.get("output_dir"))
        record_job_event(job.id, job.project_id, "Single agent task completed.", data={"result": result})
    elif job.job_type == "build":
        result = run_build_with_repairs(job, payload)
    elif job.job_type == "autopilot":
        result = run_project_autopilot(
            job,
            payload,
            run_build_with_repairs,
            should_cancel,
            emit_event=lambda message, level="INFO", data=None: record_job_event(job.id, job.project_id, message, level, data),
        )
    else:
        raise ValueError(f"Unsupported job type: {job.job_type}")

    mark_completed(job_id, serialize_result(result))
    record_job_event(job.id, job.project_id, f"Job completed with result status: {(result or {}).get('status', 'COMPLETED') if isinstance(result, dict) else 'COMPLETED'}.")


def main():
    if len(sys.argv) != 2:
        raise SystemExit("Usage: python -m services.job_worker <job_id>")
    job_id = int(sys.argv[1])
    try:
        run_job(job_id)
    except Exception:
        error = traceback.format_exc()
        job = get_job(job_id)
        if job is not None:
            record_job_event(job.id, job.project_id, "Job failed.", level="ERROR", data={"error": error})
        mark_failed(job_id, error)
        raise


if __name__ == "__main__":
    main()
