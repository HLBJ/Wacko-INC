from llm import model_preflight
from services.architecture_contract import ensure_project_contract
from services.company_service import run_project_tasks
from services.project_overview import project_overview
from services.project_report import build_ceo_report, save_ceo_report
from services.roadmap_service import assign_tasks_to_milestones, ensure_project_roadmap
from services.settings_service import get_settings
from services.system_blueprint import ensure_project_blueprint


def _release_summary(project_id: int) -> dict:
    report = build_ceo_report(project_id)
    if report is None:
        return {
            "ready": False,
            "blockers": ["Project not found."],
            "report": "",
        }
    return report


def run_project_autopilot(
    job,
    payload: dict,
    build_runner,
    should_cancel,
    emit_event=None,
) -> dict:
    emit_event = emit_event or (lambda message, level="INFO", data=None: None)
    max_cycles = int(payload.get("max_cycles", 8) or 8)
    max_fix_attempts = int(payload.get("max_fix_attempts", 3) or 3)
    history = []

    for cycle in range(1, max_cycles + 1):
        if should_cancel(job.id):
            return {
                "status": "CANCELLED",
                "cycles_used": cycle - 1,
                "history": history,
            }

        overview = project_overview(job.project_id, ignore_job_id=job.id)
        if overview is None:
            return {
                "status": "FAILED",
                "cycles_used": cycle - 1,
                "history": history,
                "error": "Project not found.",
            }

        recommendation = overview.get("recommended_next_action") or {}
        workflow = recommendation.get("workflow")
        emit_event(
            f"Autopilot cycle {cycle}: {recommendation.get('label', workflow)}",
            data={"workflow": workflow, "reason": recommendation.get("reason", "")},
        )
        step = {
            "cycle": cycle,
            "workflow": workflow,
            "label": recommendation.get("label", ""),
            "reason": recommendation.get("reason", ""),
        }

        if not recommendation.get("can_run", False):
            emit_event(recommendation.get("reason", "Autopilot is waiting."), level="WARN")
            step["status"] = "WAITING"
            history.append(step)
            return {
                "status": "WAITING",
                "cycles_used": cycle,
                "history": history,
                "reason": recommendation.get("reason", "Waiting for current work to finish."),
            }

        if workflow == "refresh_architecture":
            step["result"] = ensure_project_contract(job.project_id, overwrite=False)
            step["status"] = "COMPLETED"
            emit_event("Architecture contract refreshed.")
            history.append(step)
            continue

        if workflow == "refresh_blueprint":
            step["result"] = ensure_project_blueprint(job.project_id, overwrite=False)
            step["status"] = "COMPLETED"
            emit_event("System blueprint refreshed.")
            history.append(step)
            continue

        if workflow == "refresh_roadmap":
            step["result"] = ensure_project_roadmap(job.project_id, overwrite=False)
            assignment = assign_tasks_to_milestones(job.project_id)
            step["assignment"] = assignment
            step["status"] = "COMPLETED"
            emit_event("Project roadmap refreshed.", data={"assignment": assignment})
            history.append(step)
            continue

        if workflow == "run_agents":
            preflight = model_preflight(["developer", "security", "testing"])
            if not preflight["ok"]:
                emit_event(preflight["message"], level="ERROR", data=preflight)
                step["status"] = "BLOCKED"
                step["preflight"] = preflight
                history.append(step)
                return {
                    "status": "BLOCKED",
                    "cycles_used": cycle,
                    "history": history,
                    "reason": preflight["message"],
                }
            step["result"] = run_project_tasks(
                job.project_id,
                skip_task_ids=set(payload.get("skip_task_ids", [])),
                output_dir=payload.get("output_dir") or overview["project"]["project_path"],
            )
            step["status"] = "COMPLETED"
            emit_event("Agent task run completed.", data={"result_count": len(step["result"] or [])})
            history.append(step)
            continue

        if workflow == "build_until_pass":
            preflight = model_preflight(["developer", "security", "testing"])
            if not preflight["ok"]:
                emit_event(preflight["message"], level="ERROR", data=preflight)
                step["status"] = "BLOCKED"
                step["preflight"] = preflight
                history.append(step)
                return {
                    "status": "BLOCKED",
                    "cycles_used": cycle,
                    "history": history,
                    "reason": preflight["message"],
                }
            build_payload = {
                **payload,
                "project_path": payload.get("project_path") or overview["project"]["project_path"],
                "auto_fix": True,
                "max_fix_attempts": max_fix_attempts,
            }
            step["result"] = build_runner(job, build_payload)
            step["status"] = "COMPLETED"
            emit_event("Build and repair cycle completed.", data={"status": (step["result"] or {}).get("status")})
            history.append(step)
            continue

        if workflow == "release_check":
            settings = get_settings()
            report = save_ceo_report(job.project_id) if settings.get("auto_save_ceo_reports") else _release_summary(job.project_id)
            step["result"] = {
                "ready": report["ready"],
                "blockers": report["blockers"],
                "saved_path": report.get("saved_path"),
            }
            step["status"] = "READY" if report["ready"] else "NEEDS_CEO_REVIEW"
            emit_event(
                "Release check completed.",
                data={"ready": report["ready"], "blockers": report["blockers"], "saved_path": report.get("saved_path")},
            )
            history.append(step)
            return {
                "status": step["status"],
                "cycles_used": cycle,
                "history": history,
                "report": report["report"],
            }

        step["status"] = "FAILED"
        step["error"] = f"Unsupported autopilot workflow: {workflow}"
        history.append(step)
        return {
            "status": "FAILED",
            "cycles_used": cycle,
            "history": history,
            "error": step["error"],
        }

    return {
        "status": "MAX_CYCLES_REACHED",
        "cycles_used": max_cycles,
        "history": history,
    }
