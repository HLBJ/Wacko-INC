from database.db import SessionLocal
from database.models import MetricEntry


def create_metric_entry(
    metric_name: str,
    metric_value: int,
    unit: str = "count",
    source: str = "manual",
    notes: str = "",
    project_id: int | None = None,
):
    db = SessionLocal()
    try:
        entry = MetricEntry(
            project_id=project_id,
            metric_name=metric_name,
            metric_value=metric_value,
            unit=unit,
            source=source,
            notes=notes,
        )
        db.add(entry)
        db.commit()
        db.refresh(entry)
        return entry
    finally:
        db.close()


def list_metric_entries(project_id: int | None = None, metric_name: str | None = None):
    db = SessionLocal()
    try:
        query = db.query(MetricEntry)
        if project_id is not None:
            query = query.filter(MetricEntry.project_id == project_id)
        if metric_name:
            query = query.filter(MetricEntry.metric_name == metric_name)
        return query.order_by(MetricEntry.recorded_at.desc(), MetricEntry.created_at.desc()).limit(500).all()
    finally:
        db.close()


def metric_summary(project_id: int | None = None) -> dict:
    entries = list_metric_entries(project_id=project_id)
    totals = {}
    latest = {}
    for entry in entries:
        totals[entry.metric_name] = totals.get(entry.metric_name, 0) + entry.metric_value
        latest.setdefault(entry.metric_name, {
            "value": entry.metric_value,
            "unit": entry.unit,
            "recorded_at": entry.recorded_at,
        })
    return {
        "project_id": project_id,
        "totals": totals,
        "latest": latest,
        "entry_count": len(entries),
    }
