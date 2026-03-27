"""Schemas Pydantic pour l'API missions."""
from datetime import datetime
from pydantic import BaseModel


class MissionRequest(BaseModel):
    mission_type: str
    input_text: str
    conversation_id: str | None = None
    title: str | None = None


class MissionResponse(BaseModel):
    id: str
    mission_type: str
    title: str
    status: str
    progress: int
    result_content: str | None
    openclaw_agent: str
    tokens_used: int
    cost_eur: float
    error: str | None
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None


class MissionPollResponse(BaseModel):
    id: str
    status: str
    progress: int
    result_content: str | None
    error: str | None


class MissionTypeInfo(BaseModel):
    type: str
    label: str
    description: str
    icon: str


class MissionStartResponse(BaseModel):
    id: str
    status: str
    message: str
