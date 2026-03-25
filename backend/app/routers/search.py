"""
THÉRÈSE Server - Recherche globale

Endpoint de recherche unifiée (conversations, contacts, tâches).
"""

import logging

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.auth.rbac import CurrentUser
from app.auth.tenant import scope_query
from app.models.database import get_session
from app.models.entities import Contact, Conversation, Task

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/search", tags=["search"])


class SearchResult(BaseModel):
    type: str  # "conversation", "contact", "task"
    id: str
    title: str
    subtitle: str | None = None


class SearchResponse(BaseModel):
    query: str
    results: list[SearchResult]
    total: int


@router.get("", response_model=SearchResponse)
async def global_search(
    q: str = Query(..., min_length=2, max_length=200, description="Terme de recherche"),
    limit: int = Query(20, ge=1, le=50),
    current_user: CurrentUser = None,
    session: AsyncSession = Depends(get_session),
):
    """Recherche globale dans les conversations, contacts et tâches."""
    results: list[SearchResult] = []
    term = f"%{q.lower()}%"

    # Conversations
    stmt = select(Conversation).where(Conversation.title.ilike(term)).limit(limit)
    if current_user:
        stmt = scope_query(stmt, Conversation, current_user)
    convs = (await session.execute(stmt)).scalars().all()
    for c in convs:
        results.append(SearchResult(
            type="conversation",
            id=c.id,
            title=c.title or "Sans titre",
            subtitle=f"{c.message_count} messages" if hasattr(c, "message_count") else None,
        ))

    # Contacts
    stmt = select(Contact).where(
        Contact.first_name.ilike(term)
        | Contact.last_name.ilike(term)
        | Contact.company.ilike(term)
        | Contact.email.ilike(term)
    ).limit(limit)
    if current_user:
        stmt = scope_query(stmt, Contact, current_user)
    contacts = (await session.execute(stmt)).scalars().all()
    for c in contacts:
        name = " ".join(filter(None, [c.first_name, c.last_name]))
        results.append(SearchResult(
            type="contact",
            id=c.id,
            title=name or c.email or "Sans nom",
            subtitle=c.company,
        ))

    # Tâches
    stmt = select(Task).where(
        Task.title.ilike(term) | Task.description.ilike(term)
    ).limit(limit)
    if current_user:
        stmt = scope_query(stmt, Task, current_user)
    tasks = (await session.execute(stmt)).scalars().all()
    for t in tasks:
        results.append(SearchResult(
            type="task",
            id=t.id,
            title=t.title,
            subtitle=f"{t.status} - {t.priority}",
        ))

    return SearchResponse(query=q, results=results[:limit], total=len(results))
