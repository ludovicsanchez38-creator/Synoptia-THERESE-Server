"""
Thérèse Server - Memory Router (simplified)

Lightweight CRUD for contacts and projects with multi-tenant scoping.
No heavy dependencies (Qdrant, sentence_transformers, scoring).
"""

import json
import logging
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.auth.rbac import CurrentUser
from app.auth.tenant import get_owned, scope_query, set_owner
from app.models.database import get_session
from app.models.entities import Contact, Project

logger = logging.getLogger(__name__)

router = APIRouter()


# ============================================================
# Pydantic Schemas
# ============================================================


class ContactCreateRequest(BaseModel):
    """Create contact request."""

    first_name: str | None = None
    last_name: str | None = None
    company: str | None = None
    email: str | None = None
    phone: str | None = None
    address: str | None = None
    notes: str | None = None
    tags: list[str] | None = None
    stage: str = "contact"
    source: str | None = None


class ContactUpdateRequest(BaseModel):
    """Update contact request."""

    first_name: str | None = None
    last_name: str | None = None
    company: str | None = None
    email: str | None = None
    phone: str | None = None
    address: str | None = None
    notes: str | None = None
    tags: list[str] | None = None
    stage: str | None = None
    source: str | None = None


class ContactOut(BaseModel):
    """Contact response."""

    id: str
    first_name: str | None = None
    last_name: str | None = None
    company: str | None = None
    email: str | None = None
    phone: str | None = None
    address: str | None = None
    notes: str | None = None
    tags: list[str] | None = None
    stage: str = "contact"
    score: int = 50
    source: str | None = None
    last_interaction: datetime | None = None
    created_at: datetime
    updated_at: datetime


class ProjectCreateRequest(BaseModel):
    """Create project request."""

    name: str
    description: str | None = None
    contact_id: str | None = None
    status: str = "active"
    budget: float | None = None
    notes: str | None = None
    tags: list[str] | None = None


class ProjectOut(BaseModel):
    """Project response."""

    id: str
    name: str
    description: str | None = None
    contact_id: str | None = None
    status: str = "active"
    budget: float | None = None
    notes: str | None = None
    tags: list[str] | None = None
    created_at: datetime
    updated_at: datetime


# ============================================================
# Helpers
# ============================================================


def _contact_to_out(contact: Contact) -> ContactOut:
    """Convert Contact entity to response schema."""
    return ContactOut(
        id=contact.id,
        first_name=contact.first_name,
        last_name=contact.last_name,
        company=contact.company,
        email=contact.email,
        phone=contact.phone,
        address=contact.address,
        notes=contact.notes,
        tags=json.loads(contact.tags) if contact.tags else None,
        stage=contact.stage,
        score=contact.score,
        source=contact.source,
        last_interaction=contact.last_interaction,
        created_at=contact.created_at,
        updated_at=contact.updated_at,
    )


def _project_to_out(project: Project) -> ProjectOut:
    """Convert Project entity to response schema."""
    return ProjectOut(
        id=project.id,
        name=project.name,
        description=project.description,
        contact_id=project.contact_id,
        status=project.status,
        budget=project.budget,
        notes=project.notes,
        tags=json.loads(project.tags) if project.tags else None,
        created_at=project.created_at,
        updated_at=project.updated_at,
    )


# ============================================================
# Contact Endpoints
# ============================================================


@router.get("/contacts", response_model=list[ContactOut])
async def list_contacts(
    current_user: CurrentUser,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_session),
):
    """List contacts scoped to the current user."""
    stmt = select(Contact).order_by(Contact.updated_at.desc())
    stmt = scope_query(stmt, Contact, current_user)
    result = await session.execute(stmt.offset(offset).limit(limit))
    return [_contact_to_out(c) for c in result.scalars().all()]


@router.post("/contacts", response_model=ContactOut, status_code=201)
async def create_contact(
    request: ContactCreateRequest,
    current_user: CurrentUser,
    session: AsyncSession = Depends(get_session),
):
    """Create a new contact owned by the current user."""
    contact = Contact(
        first_name=request.first_name,
        last_name=request.last_name,
        company=request.company,
        email=request.email,
        phone=request.phone,
        address=request.address,
        notes=request.notes,
        tags=json.dumps(request.tags) if request.tags else None,
        stage=request.stage,
        source=request.source,
        last_interaction=datetime.utcnow(),
    )
    set_owner(contact, current_user)
    session.add(contact)
    await session.commit()
    await session.refresh(contact)
    logger.info("Contact created: %s (user=%s)", contact.id, current_user.id)
    return _contact_to_out(contact)


@router.get("/contacts/{contact_id}", response_model=ContactOut)
async def get_contact(
    contact_id: str,
    current_user: CurrentUser,
    session: AsyncSession = Depends(get_session),
):
    """Get a specific contact owned by the current user."""
    contact = await get_owned(session, Contact, contact_id, current_user)
    if not contact:
        raise HTTPException(status_code=404, detail="Contact introuvable")
    return _contact_to_out(contact)


@router.put("/contacts/{contact_id}", response_model=ContactOut)
async def update_contact(
    contact_id: str,
    request: ContactUpdateRequest,
    current_user: CurrentUser,
    session: AsyncSession = Depends(get_session),
):
    """Update a contact owned by the current user."""
    contact = await get_owned(session, Contact, contact_id, current_user)
    if not contact:
        raise HTTPException(status_code=404, detail="Contact introuvable")

    update_data = request.model_dump(exclude_unset=True)
    if "tags" in update_data:
        update_data["tags"] = (
            json.dumps(update_data["tags"]) if update_data["tags"] else None
        )

    for key, value in update_data.items():
        setattr(contact, key, value)

    contact.updated_at = datetime.utcnow()
    contact.last_interaction = datetime.utcnow()

    await session.commit()
    await session.refresh(contact)
    logger.info("Contact updated: %s (user=%s)", contact_id, current_user.id)
    return _contact_to_out(contact)


@router.delete("/contacts/{contact_id}")
async def delete_contact(
    contact_id: str,
    current_user: CurrentUser,
    session: AsyncSession = Depends(get_session),
):
    """Delete a contact owned by the current user."""
    contact = await get_owned(session, Contact, contact_id, current_user)
    if not contact:
        raise HTTPException(status_code=404, detail="Contact introuvable")

    await session.delete(contact)
    await session.commit()
    logger.info("Contact deleted: %s (user=%s)", contact_id, current_user.id)
    return {"deleted": True, "id": contact_id}


# ============================================================
# Project Endpoints
# ============================================================


@router.get("/projects", response_model=list[ProjectOut])
async def list_projects(
    current_user: CurrentUser,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    status: str | None = Query(default=None),
    session: AsyncSession = Depends(get_session),
):
    """List projects scoped to the current user."""
    stmt = select(Project).order_by(Project.updated_at.desc())
    stmt = scope_query(stmt, Project, current_user)
    if status:
        stmt = stmt.where(Project.status == status)
    result = await session.execute(stmt.offset(offset).limit(limit))
    return [_project_to_out(p) for p in result.scalars().all()]


@router.post("/projects", response_model=ProjectOut, status_code=201)
async def create_project(
    request: ProjectCreateRequest,
    current_user: CurrentUser,
    session: AsyncSession = Depends(get_session),
):
    """Create a new project owned by the current user."""
    if request.contact_id:
        contact = await get_owned(
            session, Contact, request.contact_id, current_user
        )
        if not contact:
            raise HTTPException(status_code=404, detail="Contact introuvable")

    project = Project(
        name=request.name,
        description=request.description,
        contact_id=request.contact_id,
        status=request.status,
        budget=request.budget,
        notes=request.notes,
        tags=json.dumps(request.tags) if request.tags else None,
    )
    set_owner(project, current_user)
    session.add(project)
    await session.commit()
    await session.refresh(project)
    logger.info("Project created: %s (user=%s)", project.id, current_user.id)
    return _project_to_out(project)
