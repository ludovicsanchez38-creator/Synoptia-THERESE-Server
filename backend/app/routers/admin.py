"""
Therese Server - Admin Router (P0-6)

Dashboard KPIs, gestion utilisateurs, audit log, parametres organisation.
Tous les endpoints necessitent le role admin.
"""

import json
import logging
from datetime import UTC, datetime, timedelta

from app.auth.backend import log_audit
from app.auth.models import AuditLog, Organization, User, UserRole
from app.auth.rbac import CurrentUser, RequireAdmin
from app.models.database import get_session
from app.models.entities import Contact, Conversation, Message
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

logger = logging.getLogger(__name__)
router = APIRouter()


# --- Schemas ---


class AdminStatsResponse(BaseModel):
    total_users: int
    active_users: int
    total_conversations: int
    messages_today: int
    total_contacts: int


class UserListItem(BaseModel):
    id: str
    email: str
    name: str
    role: str
    is_active: bool
    is_verified: bool
    last_login: str | None = None
    created_at: str | None = None


class UserUpdateRequest(BaseModel):
    role: str | None = None
    is_active: bool | None = None


class AuditLogItem(BaseModel):
    id: str
    user_email: str | None = None
    action: str
    resource: str | None = None
    resource_id: str | None = None
    details_json: str | None = None
    ip_address: str | None = None
    timestamp: str


class AuditLogResponse(BaseModel):
    items: list[AuditLogItem]
    total: int
    page: int
    page_size: int


class OrgSettingsResponse(BaseModel):
    id: str
    name: str
    slug: str
    max_users: int
    max_tokens_per_day: int
    is_active: bool
    settings: dict | None = None


class OrgSettingsUpdateRequest(BaseModel):
    name: str | None = None
    max_users: int | None = None
    max_tokens_per_day: int | None = None
    settings: dict | None = None


# --- Endpoints ---


@router.get("/stats", response_model=AdminStatsResponse)
async def get_admin_stats(
    current_user: User = RequireAdmin,
    session: AsyncSession = Depends(get_session),
):
    """KPIs du tableau de bord administrateur."""
    org_id = current_user.org_id

    # Total et actifs
    result = await session.execute(
        select(func.count(User.id)).where(User.org_id == org_id)
    )
    total_users = result.scalar_one()

    result = await session.execute(
        select(func.count(User.id)).where(
            User.org_id == org_id, User.is_active == True  # noqa: E712
        )
    )
    active_users = result.scalar_one()

    # Conversations dans l organisation
    result = await session.execute(
        select(func.count(Conversation.id)).where(Conversation.org_id == org_id)
    )
    total_conversations = result.scalar_one()

    # Messages aujourd hui
    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    # Sous-requete : IDs des conversations de l org
    conv_ids_stmt = select(Conversation.id).where(Conversation.org_id == org_id)
    result = await session.execute(
        select(func.count(Message.id)).where(
            Message.conversation_id.in_(conv_ids_stmt),
            Message.created_at >= today_start,
        )
    )
    messages_today = result.scalar_one()

    # Contacts dans l organisation
    result = await session.execute(
        select(func.count(Contact.id)).where(Contact.org_id == org_id)
    )
    total_contacts = result.scalar_one()

    return AdminStatsResponse(
        total_users=total_users,
        active_users=active_users,
        total_conversations=total_conversations,
        messages_today=messages_today,
        total_contacts=total_contacts,
    )


@router.get("/users", response_model=list[UserListItem])
async def list_users(
    current_user: User = RequireAdmin,
    session: AsyncSession = Depends(get_session),
):
    """Liste des utilisateurs de l organisation."""
    result = await session.execute(
        select(User)
        .where(User.org_id == current_user.org_id)
        .order_by(User.created_at.desc())
    )
    users = result.scalars().all()

    return [
        UserListItem(
            id=u.id,
            email=u.email,
            name=u.name,
            role=u.role,
            is_active=u.is_active,
            is_verified=u.is_verified,
            last_login=u.last_login.isoformat() if u.last_login else None,
            created_at=u.created_at.isoformat() if u.created_at else None,
        )
        for u in users
    ]


@router.put("/users/{user_id}", response_model=UserListItem)
async def update_user(
    user_id: str,
    body: UserUpdateRequest,
    request: Request,
    current_user: User = RequireAdmin,
    session: AsyncSession = Depends(get_session),
):
    """Modifier le role ou le statut d un utilisateur."""
    result = await session.execute(
        select(User).where(User.id == user_id, User.org_id == current_user.org_id)
    )
    target = result.scalar_one_or_none()
    if not target:
        raise HTTPException(status_code=404, detail="Utilisateur introuvable")

    # Empecher de se desactiver soi-meme
    if target.id == current_user.id and body.is_active is False:
        raise HTTPException(
            status_code=400,
            detail="Impossible de desactiver votre propre compte",
        )

    changes = {}
    if body.role is not None:
        valid_roles = [r.value for r in UserRole]
        if body.role not in valid_roles:
            raise HTTPException(
                status_code=400,
                detail=f"Role invalide. Valeurs acceptees : {valid_roles}",
            )
        changes["role"] = body.role
        target.role = body.role

    if body.is_active is not None:
        changes["is_active"] = body.is_active
        target.is_active = body.is_active

    target.updated_at = datetime.utcnow()
    await session.commit()

    # Audit
    await log_audit(
        session=session,
        user_id=current_user.id,
        org_id=current_user.org_id,
        action="admin_update_user",
        resource="users",
        resource_id=user_id,
        details_json=json.dumps(changes),
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        user_email=current_user.email,
    )

    return UserListItem(
        id=target.id,
        email=target.email,
        name=target.name,
        role=target.role,
        is_active=target.is_active,
        is_verified=target.is_verified,
        last_login=target.last_login.isoformat() if target.last_login else None,
        created_at=target.created_at.isoformat() if target.created_at else None,
    )


@router.delete("/users/{user_id}")
async def deactivate_user(
    user_id: str,
    request: Request,
    current_user: User = RequireAdmin,
    session: AsyncSession = Depends(get_session),
):
    """Desactiver un utilisateur (soft delete)."""
    result = await session.execute(
        select(User).where(User.id == user_id, User.org_id == current_user.org_id)
    )
    target = result.scalar_one_or_none()
    if not target:
        raise HTTPException(status_code=404, detail="Utilisateur introuvable")

    if target.id == current_user.id:
        raise HTTPException(
            status_code=400,
            detail="Impossible de desactiver votre propre compte",
        )

    target.is_active = False
    target.updated_at = datetime.utcnow()
    await session.commit()

    await log_audit(
        session=session,
        user_id=current_user.id,
        org_id=current_user.org_id,
        action="admin_deactivate_user",
        resource="users",
        resource_id=user_id,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        user_email=current_user.email,
    )

    return {"success": True, "message": "Utilisateur desactive"}


@router.get("/audit", response_model=AuditLogResponse)
async def get_audit_logs(
    current_user: User = RequireAdmin,
    session: AsyncSession = Depends(get_session),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    action: str | None = None,
    user_id: str | None = None,
):
    """Journal d audit pagine et filtrable."""
    stmt = select(AuditLog).where(AuditLog.org_id == current_user.org_id)
    count_stmt = select(func.count(AuditLog.id)).where(
        AuditLog.org_id == current_user.org_id
    )

    if action:
        stmt = stmt.where(AuditLog.action == action)
        count_stmt = count_stmt.where(AuditLog.action == action)
    if user_id:
        stmt = stmt.where(AuditLog.user_id == user_id)
        count_stmt = count_stmt.where(AuditLog.user_id == user_id)

    # Total
    result = await session.execute(count_stmt)
    total = result.scalar_one()

    # Page
    offset = (page - 1) * page_size
    stmt = stmt.order_by(AuditLog.timestamp.desc()).offset(offset).limit(page_size)
    result = await session.execute(stmt)
    logs = result.scalars().all()

    items = [
        AuditLogItem(
            id=log.id,
            user_email=log.user_email,
            action=log.action,
            resource=log.resource,
            resource_id=log.resource_id,
            details_json=log.details_json,
            ip_address=log.ip_address,
            timestamp=log.timestamp.isoformat() if log.timestamp else "",
        )
        for log in logs
    ]

    return AuditLogResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/org/settings", response_model=OrgSettingsResponse)
async def get_org_settings(
    current_user: User = RequireAdmin,
    session: AsyncSession = Depends(get_session),
):
    """Parametres de l organisation."""
    result = await session.execute(
        select(Organization).where(Organization.id == current_user.org_id)
    )
    org = result.scalar_one_or_none()
    if not org:
        raise HTTPException(status_code=404, detail="Organisation introuvable")

    settings_dict = None
    if org.settings_json:
        try:
            settings_dict = json.loads(org.settings_json)
        except json.JSONDecodeError:
            settings_dict = None

    return OrgSettingsResponse(
        id=org.id,
        name=org.name,
        slug=org.slug,
        max_users=org.max_users,
        max_tokens_per_day=org.max_tokens_per_day,
        is_active=org.is_active,
        settings=settings_dict,
    )


@router.put("/org/settings", response_model=OrgSettingsResponse)
async def update_org_settings(
    body: OrgSettingsUpdateRequest,
    request: Request,
    current_user: User = RequireAdmin,
    session: AsyncSession = Depends(get_session),
):
    """Modifier les parametres de l organisation."""
    result = await session.execute(
        select(Organization).where(Organization.id == current_user.org_id)
    )
    org = result.scalar_one_or_none()
    if not org:
        raise HTTPException(status_code=404, detail="Organisation introuvable")

    changes = {}
    if body.name is not None:
        org.name = body.name
        changes["name"] = body.name
    if body.max_users is not None:
        org.max_users = body.max_users
        changes["max_users"] = body.max_users
    if body.max_tokens_per_day is not None:
        org.max_tokens_per_day = body.max_tokens_per_day
        changes["max_tokens_per_day"] = body.max_tokens_per_day
    if body.settings is not None:
        org.settings_json = json.dumps(body.settings)
        changes["settings"] = body.settings

    org.updated_at = datetime.utcnow()
    await session.commit()

    await log_audit(
        session=session,
        user_id=current_user.id,
        org_id=current_user.org_id,
        action="admin_update_org",
        resource="organizations",
        resource_id=org.id,
        details_json=json.dumps(changes),
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        user_email=current_user.email,
    )

    settings_dict = None
    if org.settings_json:
        try:
            settings_dict = json.loads(org.settings_json)
        except json.JSONDecodeError:
            settings_dict = None

    return OrgSettingsResponse(
        id=org.id,
        name=org.name,
        slug=org.slug,
        max_users=org.max_users,
        max_tokens_per_day=org.max_tokens_per_day,
        is_active=org.is_active,
        settings=settings_dict,
    )
