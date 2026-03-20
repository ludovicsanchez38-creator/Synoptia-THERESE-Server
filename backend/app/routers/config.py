"""
Thérèse Server - Config Router (simplified)

Lightweight CRUD for user preferences and LLM model listing.
No heavy dependencies (encryption, http_client, Ollama probing).
"""

import json
import logging
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.auth.rbac import CurrentUser
from app.auth.tenant import scope_query, set_owner
from app.models.database import get_session
from app.models.entities import Preference

logger = logging.getLogger(__name__)

router = APIRouter()


# ============================================================
# Pydantic Schemas
# ============================================================


class PreferenceOut(BaseModel):
    """Preference response."""

    id: str
    key: str
    value: str
    category: str = "general"
    created_at: datetime
    updated_at: datetime


class PreferenceSetRequest(BaseModel):
    """Set a preference."""

    value: str
    category: str = "general"


class LLMModelOut(BaseModel):
    """LLM model info."""

    id: str
    name: str
    provider: str
    context_window: int = 0
    description: str | None = None


# ============================================================
# Static LLM Model List
# ============================================================

_AVAILABLE_MODELS: list[dict] = [
    {
        "id": "gpt-4o",
        "name": "GPT-4o",
        "provider": "openai",
        "context_window": 128000,
        "description": "Modèle phare OpenAI, rapide et performant.",
    },
    {
        "id": "gpt-4o-mini",
        "name": "GPT-4o Mini",
        "provider": "openai",
        "context_window": 128000,
        "description": "Version compacte de GPT-4o, bon rapport qualité-prix.",
    },
    {
        "id": "claude-sonnet-4-20250514",
        "name": "Claude Sonnet 4",
        "provider": "anthropic",
        "context_window": 200000,
        "description": "Modèle équilibré Anthropic.",
    },
    {
        "id": "claude-opus-4-20250514",
        "name": "Claude Opus 4",
        "provider": "anthropic",
        "context_window": 200000,
        "description": "Modèle le plus puissant Anthropic.",
    },
    {
        "id": "gemini-2.5-flash",
        "name": "Gemini 2.5 Flash",
        "provider": "google",
        "context_window": 1000000,
        "description": "Modèle rapide Google, très grand contexte.",
    },
    {
        "id": "gemini-2.5-pro",
        "name": "Gemini 2.5 Pro",
        "provider": "google",
        "context_window": 1000000,
        "description": "Modèle avancé Google.",
    },
    {
        "id": "mistral-large-latest",
        "name": "Mistral Large",
        "provider": "mistral",
        "context_window": 128000,
        "description": "Modèle phare Mistral AI.",
    },
]


# ============================================================
# Preference Endpoints
# ============================================================


@router.get("/preferences", response_model=list[PreferenceOut])
async def list_preferences(
    current_user: CurrentUser,
    session: AsyncSession = Depends(get_session),
):
    """List all preferences for the current user."""
    stmt = select(Preference).order_by(Preference.key)
    stmt = scope_query(stmt, Preference, current_user)
    result = await session.execute(stmt)
    prefs = result.scalars().all()
    return [
        PreferenceOut(
            id=p.id,
            key=p.key,
            value=p.value,
            category=p.category,
            created_at=p.created_at,
            updated_at=p.updated_at,
        )
        for p in prefs
    ]


@router.put("/preferences/{key}", response_model=PreferenceOut)
async def set_preference(
    key: str,
    request: PreferenceSetRequest,
    current_user: CurrentUser,
    session: AsyncSession = Depends(get_session),
):
    """Set (create or update) a preference for the current user."""
    stmt = select(Preference).where(Preference.key == key)
    stmt = scope_query(stmt, Preference, current_user)
    result = await session.execute(stmt)
    pref = result.scalar_one_or_none()

    if pref:
        pref.value = request.value
        pref.category = request.category
        pref.updated_at = datetime.utcnow()
    else:
        pref = Preference(
            key=key,
            value=request.value,
            category=request.category,
        )
        set_owner(pref, current_user)
        session.add(pref)

    await session.commit()
    await session.refresh(pref)

    logger.info(
        "Preference set: %s=%s (user=%s)", key, request.value[:50], current_user.id
    )
    return PreferenceOut(
        id=pref.id,
        key=pref.key,
        value=pref.value,
        category=pref.category,
        created_at=pref.created_at,
        updated_at=pref.updated_at,
    )


# ============================================================
# LLM Models Endpoint
# ============================================================


@router.get("/llm/models", response_model=list[LLMModelOut])
async def list_llm_models(
    current_user: CurrentUser,
):
    """List available LLM models (static catalog)."""
    return [LLMModelOut(**m) for m in _AVAILABLE_MODELS]
