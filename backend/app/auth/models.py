"""
Thérèse Server - Auth Models

User, Organization and Role models for multi-tenant authentication.
Uses FastAPI-Users compatible base.
"""

from datetime import UTC, datetime
from enum import Enum
from typing import Optional
from uuid import uuid4

from sqlmodel import Field, Relationship, SQLModel


def generate_uuid() -> str:
    return str(uuid4())


class UserRole(str, Enum):
    """Rôles utilisateur."""
    ADMIN = "admin"        # DSI, administrateur système
    MANAGER = "manager"    # Chef de service
    AGENT = "agent"        # Utilisateur standard


class Organization(SQLModel, table=True):
    """Organisation (mairie, PME, etc.)."""

    __tablename__ = "organizations"

    id: str = Field(default_factory=generate_uuid, primary_key=True)
    name: str = Field(index=True)
    slug: str = Field(unique=True, index=True)
    # Configuration
    settings_json: str | None = None  # JSON : allowed_models, default_model, max_tokens, etc.
    # Limites
    max_users: int = Field(default=50)
    max_tokens_per_day: int = Field(default=100000)
    # Métadonnées
    is_active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=lambda: datetime.utcnow())
    updated_at: datetime = Field(default_factory=lambda: datetime.utcnow())

    # Relationships
    users: list["User"] = Relationship(back_populates="organization")


class User(SQLModel, table=True):
    """Utilisateur authentifié."""

    __tablename__ = "users"

    id: str = Field(default_factory=generate_uuid, primary_key=True)
    email: str = Field(unique=True, index=True)
    hashed_password: str
    name: str
    role: str = Field(default=UserRole.AGENT.value, index=True)

    # Organisation
    org_id: str = Field(foreign_key="organizations.id", index=True)

    # Statut
    is_active: bool = Field(default=True)
    is_verified: bool = Field(default=False)
    is_superuser: bool = Field(default=False)

    # Charte IA
    charter_accepted: bool = Field(default=False)
    charter_accepted_at: datetime | None = None

    # Métadonnées
    last_login: datetime | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.utcnow())
    updated_at: datetime = Field(default_factory=lambda: datetime.utcnow())

    # Relationships
    organization: Optional["Organization"] = Relationship(back_populates="users")


class AuditLog(SQLModel, table=True):
    """Journal d'audit (obligatoire secteur public)."""

    __tablename__ = "audit_logs"

    id: str = Field(default_factory=generate_uuid, primary_key=True)
    user_id: str = Field(index=True)
    org_id: str = Field(index=True)
    user_email: str | None = None

    # Action
    action: str = Field(index=True)  # login, logout, chat, upload, admin_*, etc.
    resource: str | None = None      # conversations, contacts, files, users, etc.
    resource_id: str | None = None
    details_json: str | None = None  # JSON avec contexte additionnel

    # Réseau
    ip_address: str | None = None
    user_agent: str | None = None

    # Timestamp
    timestamp: datetime = Field(default_factory=lambda: datetime.utcnow(), index=True)


class RefreshToken(SQLModel, table=True):
    """Tokens de rafraîchissement JWT."""

    __tablename__ = "refresh_tokens"

    id: str = Field(default_factory=generate_uuid, primary_key=True)
    user_id: str = Field(foreign_key="users.id", index=True)
    token: str = Field(unique=True, index=True)
    expires_at: datetime
    revoked: bool = Field(default=False)
    created_at: datetime = Field(default_factory=lambda: datetime.utcnow())
