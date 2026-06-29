from database.db import SessionLocal
from database.models import Opportunity


HIGH_VALUE_TERMS = {
    "invoice", "payment", "booking", "appointment", "lead", "crm", "customer",
    "inventory", "report", "compliance", "workflow", "automation", "support",
}
LOW_COMPLEXITY_TERMS = {
    "dashboard", "tracker", "portal", "crud", "internal", "forms", "reports",
}
HIGH_COMPLEXITY_TERMS = {
    "ai", "realtime", "video", "marketplace", "payments", "blockchain", "multi-tenant",
    "mobile app", "erp",
}


def score_opportunity(title: str, problem: str, target_customer: str, proposed_solution: str) -> dict:
    text = f"{title} {problem} {target_customer} {proposed_solution}".lower()
    score = 50
    reasons = []

    value_hits = sorted(term for term in HIGH_VALUE_TERMS if term in text)
    if value_hits:
        score += min(25, len(value_hits) * 5)
        reasons.append(f"Business-value signals: {', '.join(value_hits[:6])}.")

    if target_customer.strip():
        score += 10
        reasons.append("Target customer is identified.")
    else:
        score -= 10
        reasons.append("Target customer is unclear.")

    if len(problem.strip()) > 80:
        score += 10
        reasons.append("Problem statement has useful detail.")
    else:
        score -= 5
        reasons.append("Problem statement needs more detail.")

    low_complexity = sorted(term for term in LOW_COMPLEXITY_TERMS if term in text)
    high_complexity = sorted(term for term in HIGH_COMPLEXITY_TERMS if term in text)
    if low_complexity:
        score += 8
        reasons.append(f"Good local-first build fit: {', '.join(low_complexity[:4])}.")
    if high_complexity:
        score -= min(20, len(high_complexity) * 5)
        reasons.append(f"Higher delivery risk: {', '.join(high_complexity[:4])}.")

    score = max(0, min(100, score))
    if score >= 75:
        recommendation = "VALIDATE_NOW"
    elif score >= 55:
        recommendation = "KEEP_WARM"
    else:
        recommendation = "NEEDS_REWORK"

    return {
        "score": score,
        "recommendation": recommendation,
        "reasons": reasons,
    }


def create_opportunity(title: str, problem: str = "", target_customer: str = "", proposed_solution: str = ""):
    score = score_opportunity(title, problem, target_customer, proposed_solution)
    db = SessionLocal()
    try:
        item = Opportunity(
            title=title,
            problem=problem,
            target_customer=target_customer,
            proposed_solution=proposed_solution,
            priority_score=score["score"],
            status="VALIDATION" if score["recommendation"] == "VALIDATE_NOW" else "IDEA",
            validation_notes="\n".join(score["reasons"]),
        )
        db.add(item)
        db.commit()
        db.refresh(item)
        return item
    finally:
        db.close()


def list_opportunities(status: str | None = None):
    db = SessionLocal()
    try:
        query = db.query(Opportunity)
        if status:
            query = query.filter(Opportunity.status == status)
        return query.order_by(Opportunity.priority_score.desc(), Opportunity.updated_at.desc()).limit(200).all()
    finally:
        db.close()


def update_opportunity(opportunity_id: int, payload: dict):
    db = SessionLocal()
    try:
        item = db.query(Opportunity).filter(Opportunity.id == opportunity_id).first()
        if item is None:
            return None
        for key in ("title", "problem", "target_customer", "proposed_solution", "status", "validation_notes"):
            if key in payload and payload[key] is not None:
                setattr(item, key, payload[key])
        score = score_opportunity(item.title, item.problem, item.target_customer, item.proposed_solution)
        item.priority_score = score["score"]
        if "validation_notes" not in payload:
            item.validation_notes = "\n".join(score["reasons"])
        db.commit()
        db.refresh(item)
        return item
    finally:
        db.close()


def opportunity_goal(opportunity: Opportunity) -> str:
    return (
        f"Build a software system for this startup opportunity.\n\n"
        f"Opportunity: {opportunity.title}\n"
        f"Target customer: {opportunity.target_customer or 'Unspecified'}\n\n"
        f"Problem:\n{opportunity.problem}\n\n"
        f"Proposed solution:\n{opportunity.proposed_solution}\n\n"
        "Create the smallest useful product first, with a roadmap, system blueprint, tests, security review, and CEO approval gates."
    )


def mark_converted(opportunity_id: int, project_id: int):
    db = SessionLocal()
    try:
        item = db.query(Opportunity).filter(Opportunity.id == opportunity_id).first()
        if item is None:
            return None
        item.status = "CONVERTED"
        item.created_project_id = project_id
        db.commit()
        db.refresh(item)
        return item
    finally:
        db.close()
