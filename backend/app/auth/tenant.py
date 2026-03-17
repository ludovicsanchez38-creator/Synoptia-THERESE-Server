"""
Thérèse Server - Tenant utilities

Helpers for multi-tenant query scoping.
"""

from app.auth.models import User
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import SQLModel, select


def scope_query(stmt, model: type[SQLModel], user: User):
    """Add user_id and org_id filters to a SELECT statement."""
    if hasattr(model, "user_id"):
        stmt = stmt.where(model.user_id == user.id)
    return stmt


def scope_query_org(stmt, model: type[SQLModel], user: User):
    """Add org_id filter only (for shared resources within an org)."""
    if hasattr(model, "org_id"):
        stmt = stmt.where(model.org_id == user.org_id)
    return stmt


def set_owner(instance: SQLModel, user: User) -> None:
    """Set user_id and org_id on a model instance."""
    if hasattr(instance, "user_id"):
        instance.user_id = user.id
    if hasattr(instance, "org_id"):
        instance.org_id = user.org_id


async def get_owned(
    session: AsyncSession,
    model: type[SQLModel],
    record_id: str,
    user: User,
) -> SQLModel | None:
    """Get a record by ID, scoped to the current user."""
    stmt = select(model).where(model.id == record_id)
    stmt = scope_query(stmt, model, user)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()
