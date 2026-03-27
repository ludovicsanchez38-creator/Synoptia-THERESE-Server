"""
Thérèse Server - Auth Backend

JWT authentication with password hashing (bcrypt direct).
"""

import logging
import secrets
from datetime import UTC, datetime, timedelta

import bcrypt
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.auth.models import AuditLog, RefreshToken, User, UserRole
from app.config import settings

logger = logging.getLogger(__name__)

# JWT
try:
    from jose import JWTError, jwt
    HAS_JOSE = True
except ImportError:
    HAS_JOSE = False
    logger.warning("python-jose non installé, JWT désactivé")


def hash_password(password: str) -> str:
    """Hash a password with bcrypt."""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    """Verify a password against its bcrypt hash."""
    return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))


def create_access_token(user: User) -> str:
    """Create a JWT access token."""
    if not HAS_JOSE:
        raise RuntimeError("python-jose requis pour JWT")

    payload = {
        "sub": user.id,
        "email": user.email,
        "name": user.name,
        "role": user.role,
        "org_id": user.org_id,
        "charter_accepted": user.charter_accepted,
        "exp": datetime.utcnow() + timedelta(seconds=settings.jwt_lifetime_seconds),
        "iat": datetime.utcnow(),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm="HS256")


def create_refresh_token() -> str:
    """Create a random refresh token."""
    return secrets.token_urlsafe(64)


def decode_access_token(token: str) -> dict | None:
    """Decode and validate a JWT access token."""
    if not HAS_JOSE:
        return None
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
        return payload
    except JWTError:
        return None


async def authenticate_user(session: AsyncSession, email: str, password: str) -> User | None:
    """Authenticate a user by email and password."""
    stmt = select(User).where(User.email == email, User.is_active == True)  # noqa: E712
    result = await session.execute(stmt)
    user = result.scalar_one_or_none()

    if not user:
        return None
    if not verify_password(password, user.hashed_password):
        return None

    # Update last_login
    user.last_login = datetime.utcnow()
    session.add(user)
    await session.commit()

    return user


async def get_user_by_id(session: AsyncSession, user_id: str) -> User | None:
    """Get a user by ID."""
    stmt = select(User).where(User.id == user_id, User.is_active == True)  # noqa: E712
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def get_user_by_email(session: AsyncSession, email: str) -> User | None:
    """Get a user by email."""
    stmt = select(User).where(User.email == email)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def create_user(
    session: AsyncSession,
    email: str,
    password: str,
    name: str,
    org_id: str,
    role: str = UserRole.AGENT.value,
) -> User:
    """Create a new user."""
    user = User(
        email=email,
        hashed_password=hash_password(password),
        name=name,
        org_id=org_id,
        role=role,
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


async def log_audit(
    session: AsyncSession,
    user_id: str,
    org_id: str,
    action: str,
    resource: str | None = None,
    resource_id: str | None = None,
    details_json: str | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
    user_email: str | None = None,
) -> None:
    """Log an audit entry."""
    if not settings.audit_log_enabled:
        return

    entry = AuditLog(
        user_id=user_id,
        org_id=org_id,
        user_email=user_email,
        action=action,
        resource=resource,
        resource_id=resource_id,
        details_json=details_json,
        ip_address=ip_address,
        user_agent=user_agent,
    )
    session.add(entry)
    await session.commit()


async def store_refresh_token(
    session: AsyncSession, user_id: str, token: str
) -> RefreshToken:
    """Store a refresh token."""
    rt = RefreshToken(
        user_id=user_id,
        token=token,
        expires_at=datetime.utcnow() + timedelta(seconds=settings.jwt_refresh_lifetime_seconds),
    )
    session.add(rt)
    await session.commit()
    return rt


async def validate_refresh_token(
    session: AsyncSession, token: str
) -> User | None:
    """Validate a refresh token and return the user."""
    stmt = select(RefreshToken).where(
        RefreshToken.token == token,
        RefreshToken.revoked == False,  # noqa: E712
        RefreshToken.expires_at > datetime.utcnow(),
    )
    result = await session.execute(stmt)
    rt = result.scalar_one_or_none()
    if not rt:
        return None

    return await get_user_by_id(session, rt.user_id)


async def revoke_refresh_token(session: AsyncSession, token: str) -> None:
    """Revoke a refresh token."""
    stmt = select(RefreshToken).where(RefreshToken.token == token)
    result = await session.execute(stmt)
    rt = result.scalar_one_or_none()
    if rt:
        rt.revoked = True
        session.add(rt)
        await session.commit()
