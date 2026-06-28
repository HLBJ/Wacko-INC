from sqlalchemy import inspect, text

from database.db import Base, engine
import database.models  # noqa


def ensure_schema():
    Base.metadata.create_all(bind=engine)

    inspector = inspect(engine)
    tables = set(inspector.get_table_names())
    project_columns = {column["name"] for column in inspector.get_columns("projects")} if "projects" in tables else set()
    agent_run_columns = {column["name"] for column in inspector.get_columns("agent_runs")}
    task_columns = {column["name"] for column in inspector.get_columns("tasks")}
    build_run_columns = {column["name"] for column in inspector.get_columns("build_runs")} if "build_runs" in tables else set()
    job_columns = {column["name"] for column in inspector.get_columns("jobs")} if "jobs" in tables else set()

    with engine.begin() as connection:
        if "projects" in tables and "project_path" not in project_columns:
            connection.execute(text("ALTER TABLE projects ADD COLUMN project_path TEXT DEFAULT ''"))
        if "output_file" not in agent_run_columns:
            connection.execute(text("ALTER TABLE agent_runs ADD COLUMN output_file TEXT DEFAULT ''"))
        if "output_files" not in agent_run_columns:
            connection.execute(text("ALTER TABLE agent_runs ADD COLUMN output_files TEXT DEFAULT ''"))
        if "branch_name" not in agent_run_columns:
            connection.execute(text("ALTER TABLE agent_runs ADD COLUMN branch_name VARCHAR DEFAULT ''"))
        if "branch_name" not in task_columns:
            connection.execute(text("ALTER TABLE tasks ADD COLUMN branch_name VARCHAR DEFAULT ''"))
        if "build_runs" in tables and "branch_name" not in build_run_columns:
            connection.execute(text("ALTER TABLE build_runs ADD COLUMN branch_name VARCHAR DEFAULT ''"))
        if "jobs" in tables and "retry_of_job_id" not in job_columns:
            connection.execute(text("ALTER TABLE jobs ADD COLUMN retry_of_job_id INTEGER"))
        if "jobs" in tables and "cancel_requested" not in job_columns:
            connection.execute(text("ALTER TABLE jobs ADD COLUMN cancel_requested INTEGER DEFAULT 0"))
        if "jobs" in tables and "payload_json" not in job_columns:
            connection.execute(text("ALTER TABLE jobs ADD COLUMN payload_json TEXT DEFAULT ''"))
        if "jobs" in tables and "process_id" not in job_columns:
            connection.execute(text("ALTER TABLE jobs ADD COLUMN process_id INTEGER"))

    if "build_runs" not in tables or "jobs" not in tables:
        Base.metadata.create_all(bind=engine)
