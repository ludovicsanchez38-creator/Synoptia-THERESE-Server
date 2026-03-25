"""
Thérèse Server - Chat Router (simplifié)

CRUD conversations + messages. Le streaming LLM sera activé avec Docker.
"""

import logging
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.auth.rbac import CurrentUser
from app.auth.tenant import get_owned, scope_query, set_owner
from app.models.database import get_session
from app.models.entities import Conversation, Message

logger = logging.getLogger(__name__)
router = APIRouter()


# --- Schemas ---

class ConversationCreate(BaseModel):
    title: str | None = None

class ConversationResponse(BaseModel):
    id: str
    title: str | None
    message_count: int = 0
    created_at: datetime
    updated_at: datetime

class MessageCreate(BaseModel):
    content: str
    role: str = "user"

class MessageResponse(BaseModel):
    id: str
    conversation_id: str
    role: str
    content: str
    model: str | None = None
    created_at: datetime


# --- Conversations CRUD ---

@router.get("/conversations", response_model=list[ConversationResponse])
async def list_conversations(
    current_user: CurrentUser,
    limit: int = 50,
    offset: int = 0,
    session: AsyncSession = Depends(get_session),
):
    """Lister les conversations de l'utilisateur."""
    stmt = (
        select(
            Conversation,
            func.count(Message.id).label("message_count"),
        )
        .outerjoin(Message, Message.conversation_id == Conversation.id)
        .group_by(Conversation.id)
        .order_by(Conversation.updated_at.desc())
        .offset(offset)
        .limit(limit)
    )
    stmt = scope_query(stmt, Conversation, current_user)
    result = await session.execute(stmt)
    rows = result.all()

    return [
        ConversationResponse(
            id=conv.id,
            title=conv.title,
            message_count=count,
            created_at=conv.created_at,
            updated_at=conv.updated_at,
        )
        for conv, count in rows
    ]


@router.post("/conversations", response_model=ConversationResponse)
async def create_conversation(
    data: ConversationCreate,
    current_user: CurrentUser,
    session: AsyncSession = Depends(get_session),
):
    """Créer une conversation."""
    conversation = Conversation(title=data.title)
    set_owner(conversation, current_user)
    session.add(conversation)
    await session.commit()
    await session.refresh(conversation)

    return ConversationResponse(
        id=conversation.id,
        title=conversation.title,
        message_count=0,
        created_at=conversation.created_at,
        updated_at=conversation.updated_at,
    )


@router.get("/conversations/{conversation_id}", response_model=ConversationResponse)
async def get_conversation(
    conversation_id: str,
    current_user: CurrentUser,
    session: AsyncSession = Depends(get_session),
):
    """Récupérer une conversation."""
    conversation = await get_owned(session, Conversation, conversation_id, current_user)
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation introuvable")

    # Count messages
    stmt = select(func.count(Message.id)).where(Message.conversation_id == conversation_id)
    result = await session.execute(stmt)
    count = result.scalar() or 0

    return ConversationResponse(
        id=conversation.id,
        title=conversation.title,
        message_count=count,
        created_at=conversation.created_at,
        updated_at=conversation.updated_at,
    )


@router.get("/conversations/{conversation_id}/messages", response_model=list[MessageResponse])
async def get_conversation_messages(
    conversation_id: str,
    current_user: CurrentUser,
    limit: int = 100,
    session: AsyncSession = Depends(get_session),
):
    """Messages d'une conversation."""
    # Vérifier que la conversation appartient à l'utilisateur
    conversation = await get_owned(session, Conversation, conversation_id, current_user)
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation introuvable")

    stmt = (
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at)
        .limit(limit)
    )
    result = await session.execute(stmt)
    messages = result.scalars().all()

    return [
        MessageResponse(
            id=m.id,
            conversation_id=m.conversation_id,
            role=m.role,
            content=m.content,
            model=m.model,
            created_at=m.created_at,
        )
        for m in messages
    ]


@router.delete("/conversations/{conversation_id}")
async def delete_conversation(
    conversation_id: str,
    current_user: CurrentUser,
    session: AsyncSession = Depends(get_session),
):
    """Supprimer une conversation et ses messages."""
    conversation = await get_owned(session, Conversation, conversation_id, current_user)
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation introuvable")

    await session.delete(conversation)
    await session.commit()

    return {"detail": "Conversation supprimée"}


@router.post("/conversations/{conversation_id}/messages", response_model=MessageResponse)
async def add_message(
    conversation_id: str,
    data: MessageCreate,
    current_user: CurrentUser,
    session: AsyncSession = Depends(get_session),
):
    """Ajouter un message à une conversation (sans LLM pour l'instant)."""
    conversation = await get_owned(session, Conversation, conversation_id, current_user)
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation introuvable")

    message = Message(
        conversation_id=conversation_id,
        role=data.role,
        content=data.content,
    )
    session.add(message)

    # Mettre à jour le timestamp de la conversation
    conversation.updated_at = datetime.utcnow()
    session.add(conversation)

    await session.commit()
    await session.refresh(message)

    return MessageResponse(
        id=message.id,
        conversation_id=message.conversation_id,
        role=message.role,
        content=message.content,
        model=message.model,
        created_at=message.created_at,
    )
