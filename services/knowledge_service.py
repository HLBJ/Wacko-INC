import re

from database.db import SessionLocal
from database.models import KnowledgeArticle


def _tokens(text: str) -> set[str]:
    return {token for token in re.findall(r"[a-z0-9]{3,}", text.lower())}


def create_article(project_id: int | None, title: str, body: str, tags: str = ""):
    db = SessionLocal()
    try:
        article = KnowledgeArticle(project_id=project_id, title=title, body=body, tags=tags)
        db.add(article)
        db.commit()
        db.refresh(article)
        return article
    finally:
        db.close()


def list_articles(project_id: int | None = None, status: str | None = "ACTIVE"):
    db = SessionLocal()
    try:
        query = db.query(KnowledgeArticle)
        if project_id is not None:
            query = query.filter(KnowledgeArticle.project_id == project_id)
        if status:
            query = query.filter(KnowledgeArticle.status == status)
        return query.order_by(KnowledgeArticle.updated_at.desc()).limit(200).all()
    finally:
        db.close()


def update_article(article_id: int, payload: dict):
    db = SessionLocal()
    try:
        article = db.query(KnowledgeArticle).filter(KnowledgeArticle.id == article_id).first()
        if article is None:
            return None
        for key in ("title", "body", "tags", "status"):
            if key in payload and payload[key] is not None:
                setattr(article, key, payload[key])
        db.commit()
        db.refresh(article)
        return article
    finally:
        db.close()


def search_articles(query_text: str, project_id: int | None = None, limit: int = 5) -> list[dict]:
    query_tokens = _tokens(query_text)
    if not query_tokens:
        return []

    articles = list_articles(project_id=project_id, status="ACTIVE")
    ranked = []
    for article in articles:
        article_text = f"{article.title}\n{article.tags}\n{article.body}"
        article_tokens = _tokens(article_text)
        score = len(query_tokens & article_tokens)
        if score:
            ranked.append({
                "id": article.id,
                "project_id": article.project_id,
                "title": article.title,
                "body": article.body,
                "tags": article.tags,
                "score": score,
            })

    ranked.sort(key=lambda item: (-item["score"], item["title"].lower()))
    return ranked[:limit]
