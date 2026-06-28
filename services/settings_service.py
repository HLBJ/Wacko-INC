import os

from database.db import SessionLocal
from database.models import Setting


DEFAULT_SETTINGS = {
    "output_base_dir": os.getenv("OUTPUT_BASE_DIR", "C:/Project"),
    "max_fix_attempts": "3",
    "max_autopilot_cycles": "8",
    "local_only": "true",
    "auto_save_ceo_reports": "true",
}


def _serialize(value) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def _typed(key: str, value: str):
    if key in {"max_fix_attempts", "max_autopilot_cycles"}:
        try:
            return int(value)
        except (TypeError, ValueError):
            return int(DEFAULT_SETTINGS[key])
    if key in {"local_only", "auto_save_ceo_reports"}:
        return str(value).strip().lower() in {"1", "true", "yes", "on"}
    return value


def get_settings() -> dict:
    db = SessionLocal()
    try:
        rows = db.query(Setting).all()
        values = dict(DEFAULT_SETTINGS)
        values.update({row.key: row.value for row in rows})
        return {key: _typed(key, value) for key, value in values.items()}
    finally:
        db.close()


def update_settings(payload: dict) -> dict:
    allowed = set(DEFAULT_SETTINGS)
    db = SessionLocal()
    try:
        for key, value in payload.items():
            if key not in allowed or value is None:
                continue
            row = db.query(Setting).filter(Setting.key == key).first()
            if row is None:
                row = Setting(key=key, value=_serialize(value))
                db.add(row)
            else:
                row.value = _serialize(value)
        db.commit()
    finally:
        db.close()
    return get_settings()
