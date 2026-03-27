"""Thérèse Server - Mission Models for autonomous agents."""
from datetime import datetime
from enum import Enum
from sqlmodel import Field, SQLModel
from app.models.entities import generate_uuid


class MissionType(str, Enum):
    CONFORMITY = "conformity"
    RESEARCH = "research"
    DOCUMENT = "document"
    CRM = "crm"


class MissionStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMEOUT = "timeout"


class Mission(SQLModel, table=True):
    __tablename__ = "missions"

    id: str = Field(default_factory=generate_uuid, primary_key=True)
    user_id: str = Field(foreign_key="users.id", index=True)
    org_id: str = Field(index=True)
    conversation_id: str | None = Field(default=None, index=True)

    mission_type: str = Field(index=True)
    title: str = Field(default="")
    input_text: str = Field(default="")

    status: str = Field(default=MissionStatus.PENDING.value, index=True)
    result_content: str | None = Field(default=None)
    progress: int = Field(default=0)

    openclaw_agent: str = Field(default="")
    tokens_used: int = Field(default=0)
    cost_eur: float = Field(default=0.0)
    max_tokens: int = Field(default=200000)
    timeout_seconds: int = Field(default=300)

    error: str | None = Field(default=None)
    started_at: datetime | None = Field(default=None)
    completed_at: datetime | None = Field(default=None)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
