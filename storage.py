from database.db import SessionLocal
from database.models import Execution


def save_log(stage: str, input_text: str, output_text: str):
    db = SessionLocal()

    try:
        record = Execution(
            stage=stage,
            input_text=input_text,
            output_text=output_text
        )

        db.add(record)
        db.commit()

    finally:
        db.close()