"""
Thérèse Server - RBAC (Role-Based Access Control)

FastAPI dependencies for authentication and authorization.
"""

import json
import logging
from typing import Annotated

from app.auth.backend import decode_access_token, get_user_by_id, log_audit
from app.auth.models import User, UserRole
from app.models.database import get_session
from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


async def get_current_user(
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> User:
    """Extract and validate the current user from JWT token."""
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token d'authentification requis",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = auth_header.split(" ", 1)[1]
    payload = decode_access_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token invalide ou expiré",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = await get_user_by_id(session, payload["sub"])
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Utilisateur introuvable",
        )

    return user


# Type alias pour injection de dépendances
CurrentUser = Annotated[User, Depends(get_current_user)]


def require_role(*roles: str):
    """Dependency factory : require specific roles."""

    async def _check_role(current_user: CurrentUser) -> User:
        if current_user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Rôle requis : {', '.join(roles)}",
            )
        return current_user

    return Depends(_check_role)


# Raccourcis
RequireAdmin = require_role(UserRole.ADMIN.value)
RequireManager = require_role(UserRole.ADMIN.value, UserRole.MANAGER.value)
RequireAgent = require_role(UserRole.ADMIN.value, UserRole.MANAGER.value, UserRole.AGENT.value)


async def audit_action(
    request: Request,
    current_user: CurrentUser,
    session: AsyncSession = Depends(get_session),
    action: str = "",
    resource: str | None = None,
    resource_id: str | None = None,
    details: dict | None = None,
) -> None:
    """Log an audit action for the current user."""
    await log_audit(
        session=session,
        user_id=current_user.id,
        org_id=current_user.org_id,
        action=action,
        resource=resource,
        resource_id=resource_id,
        details_json=json.dumps(details) if details else None,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        user_email=current_user.email,
    )
