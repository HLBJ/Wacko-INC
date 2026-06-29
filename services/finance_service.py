from database.db import SessionLocal
from database.models import FinanceEntry


def create_finance_entry(
    amount: float,
    entry_type: str = "EXPENSE",
    category: str = "",
    description: str = "",
    currency: str = "ZAR",
    project_id: int | None = None,
):
    normalized_type = entry_type.upper()
    if normalized_type not in {"REVENUE", "EXPENSE"}:
        normalized_type = "EXPENSE"
    amount_cents = int(round(abs(amount) * 100))
    db = SessionLocal()
    try:
        entry = FinanceEntry(
            project_id=project_id,
            entry_type=normalized_type,
            category=category,
            description=description,
            amount_cents=amount_cents,
            currency=currency.upper() or "ZAR",
        )
        db.add(entry)
        db.commit()
        db.refresh(entry)
        return entry
    finally:
        db.close()


def list_finance_entries(project_id: int | None = None, currency: str | None = None):
    db = SessionLocal()
    try:
        query = db.query(FinanceEntry)
        if project_id is not None:
            query = query.filter(FinanceEntry.project_id == project_id)
        if currency:
            query = query.filter(FinanceEntry.currency == currency.upper())
        return query.order_by(FinanceEntry.occurred_at.desc(), FinanceEntry.created_at.desc()).limit(500).all()
    finally:
        db.close()


def finance_summary(project_id: int | None = None, currency: str = "ZAR") -> dict:
    entries = list_finance_entries(project_id=project_id, currency=currency)
    revenue = sum(entry.amount_cents for entry in entries if entry.entry_type == "REVENUE")
    expenses = sum(entry.amount_cents for entry in entries if entry.entry_type == "EXPENSE")
    profit = revenue - expenses
    return {
        "project_id": project_id,
        "currency": currency.upper(),
        "revenue": revenue / 100,
        "expenses": expenses / 100,
        "profit": profit / 100,
        "entry_count": len(entries),
    }
