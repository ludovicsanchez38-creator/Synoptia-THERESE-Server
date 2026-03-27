"""
Thérèse Server - Auth Router

Endpoints : login, register, me, refresh, logout, charter.
"""

import json
import logging
import re as _re
import time
from collections import defaultdict
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.auth.backend import (
    authenticate_user,
    create_access_token,
    create_refresh_token,
    create_user,
    log_audit,
    revoke_refresh_token,
    store_refresh_token,
    validate_refresh_token,
)
from app.auth.models import Organization, User, UserRole
from app.auth.rbac import CurrentUser, RequireAdmin
from app.models.database import get_session

# Rate limit login: 5 tentatives par minute par IP (SEC-015)
_login_attempts: dict[str, list[float]] = defaultdict(list)
_LOGIN_MAX = 5
_LOGIN_WINDOW = 60  # secondes

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/auth", tags=["auth"])


# --- Schemas ---


class LoginRequest(BaseModel):
    username: str  # email (OAuth2 convention)
    password: str


class LoginResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RegisterRequest(BaseModel):
    email: str
    password: str
    name: str
    org_id: str | None = None
    role: str = UserRole.AGENT.value


class UserResponse(BaseModel):
    id: str
    email: str
    name: str
    role: str
    org_id: str
    org_name: str
    is_active: bool
    charter_accepted: bool
    last_login: datetime | None
    created_at: datetime


class RefreshRequest(BaseModel):
    refresh_token: str


class CharterAcceptRequest(BaseModel):
    accepted: bool


class CreateOrgRequest(BaseModel):
    name: str
    slug: str
    max_users: int = 50


# --- Password policy ---


def _validate_password(password: str) -> str:
    """Valide la politique de mot de passe (min 8 chars, 1 majuscule, 1 chiffre)."""
    if len(password) < 8:
        raise HTTPException(status_code=400, detail="Le mot de passe doit contenir au moins 8 caracteres")
    if not _re.search(r"[A-Z]", password):
        raise HTTPException(status_code=400, detail="Le mot de passe doit contenir au moins une majuscule")
    if not _re.search(r"[0-9]", password):
        raise HTTPException(status_code=400, detail="Le mot de passe doit contenir au moins un chiffre")
    return password


# --- Endpoints ---


@router.post("/login", response_model=LoginResponse)
async def login(
    request: Request,
    session: AsyncSession = Depends(get_session),
):
    """Authentifier un utilisateur (email + mot de passe).

    Rate limit: 5 tentatives par minute par IP.
    """
    # Rate limit par IP (SEC-015)
    client_ip = request.client.host if request.client else "unknown"
    now = time.time()
    _login_attempts[client_ip] = [t for t in _login_attempts[client_ip] if now - t < _LOGIN_WINDOW]
    if len(_login_attempts[client_ip]) >= _LOGIN_MAX:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Trop de tentatives de connexion. Reessayez dans quelques instants.",
        )
    _login_attempts[client_ip].append(now)

    # Parse form data (OAuth2 convention) or JSON
    content_type = request.headers.get("content-type", "")
    if "application/x-www-form-urlencoded" in content_type:
        form = await request.form()
        email = str(form.get("username", ""))
        password = str(form.get("password", ""))
    else:
        body = await request.json()
        email = body.get("username", body.get("email", ""))
        password = body.get("password", "")

    user = await authenticate_user(session, email, password)
    if not user:
        await log_audit(
            session=session,
            user_id="unknown",
            org_id="unknown",
            action="login_failed",
            details_json=json.dumps({"email": email}),
            ip_address=request.client.host if request.client else None,
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email ou mot de passe incorrect",
        )

    # Générer tokens
    access_token = create_access_token(user)
    refresh = create_refresh_token()
    await store_refresh_token(session, user.id, refresh)

    # Audit
    await log_audit(
        session=session,
        user_id=user.id,
        org_id=user.org_id,
        action="login",
        ip_address=request.client.host if request.client else None,
        user_email=user.email,
    )

    return LoginResponse(access_token=access_token, refresh_token=refresh)


@router.get("/me", response_model=UserResponse)
async def get_me(
    current_user: CurrentUser,
    session: AsyncSession = Depends(get_session),
):
    """Profil de l'utilisateur connecté."""
    # Charger le nom de l'organisation
    stmt = select(Organization).where(Organization.id == current_user.org_id)
    result = await session.execute(stmt)
    org = result.scalar_one_or_none()

    return UserResponse(
        id=current_user.id,
        email=current_user.email,
        name=current_user.name,
        role=current_user.role,
        org_id=current_user.org_id,
        org_name=org.name if org else "Inconnue",
        is_active=current_user.is_active,
        charter_accepted=current_user.charter_accepted,
        last_login=current_user.last_login,
        created_at=current_user.created_at,
    )


@router.post("/refresh", response_model=LoginResponse)
async def refresh_token(
    body: RefreshRequest,
    session: AsyncSession = Depends(get_session),
):
    """Rafraîchir le token d'accès."""
    user = await validate_refresh_token(session, body.refresh_token)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token invalide ou expiré",
        )

    # Révoquer l'ancien et créer un nouveau
    await revoke_refresh_token(session, body.refresh_token)
    new_access = create_access_token(user)
    new_refresh = create_refresh_token()
    await store_refresh_token(session, user.id, new_refresh)

    return LoginResponse(access_token=new_access, refresh_token=new_refresh)


@router.post("/logout")
async def logout(
    request: Request,
    current_user: CurrentUser,
    session: AsyncSession = Depends(get_session),
):
    """Déconnexion (révoque le refresh token si fourni)."""
    try:
        body = await request.json()
        if rt := body.get("refresh_token"):
            await revoke_refresh_token(session, rt)
    except (ValueError, KeyError) as e:
        logger.debug("Logout refresh token revocation skipped: %s", e)

    await log_audit(
        session=session,
        user_id=current_user.id,
        org_id=current_user.org_id,
        action="logout",
        ip_address=request.client.host if request.client else None,
        user_email=current_user.email,
    )

    return {"detail": "Déconnecté"}


@router.post("/charter")
async def accept_charter(
    body: CharterAcceptRequest,
    current_user: CurrentUser,
    session: AsyncSession = Depends(get_session),
):
    """Accepter la charte IA (obligatoire au premier login)."""
    current_user.charter_accepted = body.accepted
    if body.accepted:
        current_user.charter_accepted_at = datetime.utcnow()
    session.add(current_user)
    await session.commit()

    return {"detail": "Charte acceptée" if body.accepted else "Charte refusée"}


# --- Admin endpoints ---


@router.post("/users", response_model=UserResponse)
async def create_user_endpoint(
    body: RegisterRequest,
    current_user: User = RequireAdmin,
    session: AsyncSession = Depends(get_session),
):
    """Créer un utilisateur (admin uniquement)."""
    # Vérifier que l'email n'existe pas
    stmt = select(User).where(User.email == body.email)
    result = await session.execute(stmt)
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Un utilisateur avec cet email existe déjà",
        )

    _validate_password(body.password)

    org_id = body.org_id or current_user.org_id
    user = await create_user(
        session=session,
        email=body.email,
        password=body.password,
        name=body.name,
        org_id=org_id,
        role=body.role,
    )

    # Charger org name
    stmt = select(Organization).where(Organization.id == org_id)
    result = await session.execute(stmt)
    org = result.scalar_one_or_none()

    await log_audit(
        session=session,
        user_id=current_user.id,
        org_id=current_user.org_id,
        action="user_created",
        resource="users",
        resource_id=user.id,
        details_json=json.dumps({"email": body.email, "role": body.role}),
        user_email=current_user.email,
    )

    return UserResponse(
        id=user.id,
        email=user.email,
        name=user.name,
        role=user.role,
        org_id=user.org_id,
        org_name=org.name if org else "Inconnue",
        is_active=user.is_active,
        charter_accepted=user.charter_accepted,
        last_login=user.last_login,
        created_at=user.created_at,
    )


@router.get("/users")
async def list_users(
    current_user: User = RequireAdmin,
    session: AsyncSession = Depends(get_session),
):
    """Lister les utilisateurs de l'organisation (admin uniquement)."""
    stmt = select(User).where(User.org_id == current_user.org_id).order_by(User.created_at)
    result = await session.execute(stmt)
    users = result.scalars().all()

    return [
        {
            "id": u.id,
            "email": u.email,
            "name": u.name,
            "role": u.role,
            "is_active": u.is_active,
            "charter_accepted": u.charter_accepted,
            "charter_accepted_at": u.charter_accepted_at.isoformat() if u.charter_accepted_at else None,
            "last_login": u.last_login,
            "created_at": u.created_at,
        }
        for u in users
    ]


@router.post("/organizations", response_model=dict)
async def create_organization(
    body: CreateOrgRequest,
    current_user: User = RequireAdmin,
    session: AsyncSession = Depends(get_session),
):
    """Créer une organisation (superadmin)."""
    if not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Réservé aux super-administrateurs")

    stmt = select(Organization).where(Organization.slug == body.slug)
    result = await session.execute(stmt)
    if result.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Ce slug est déjà utilisé")

    org = Organization(name=body.name, slug=body.slug, max_users=body.max_users)
    session.add(org)
    await session.commit()
    await session.refresh(org)

    return {"id": org.id, "name": org.name, "slug": org.slug}


# --- Reset password ---


class ForgotPasswordRequest(BaseModel):
    email: str


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str


@router.post("/forgot-password")
async def forgot_password(
    request: ForgotPasswordRequest,
    session: AsyncSession = Depends(get_session),
):
    """
    Demande de reinitialisation de mot de passe.
    Genere un token JWT valable 1h.
    Note : retourne toujours 200 pour ne pas reveler si l'email existe.
    """
    from app.auth.backend import get_user_by_email

    user = await get_user_by_email(session, request.email)
    if user:
        # Generer un token de reset (JWT avec expiration 1h)
        from jose import jwt

        from app.config import settings

        token = jwt.encode(
            {"sub": user.id, "type": "reset", "exp": datetime.utcnow().timestamp() + 3600},
            settings.jwt_secret,
            algorithm="HS256",
        )
        # TODO: Envoyer le token par email quand le service email est configure
        # Pour l'instant, on log le token (dev only, visible dans les logs serveur)
        logger.info("Reset token genere pour %s : %s", user.email, token)

        # En mode dev, on stocke le token dans les logs d'audit
        await log_audit(
            session=session,
            user_id=user.id,
            org_id=user.org_id,
            action="password_reset_requested",
            resource="auth",
            details_json=json.dumps({"email": user.email}),
        )

    return {"message": "Si un compte existe avec cet email, un lien de reinitialisation a ete envoye."}


@router.post("/reset-password")
async def reset_password(
    request: ResetPasswordRequest,
    session: AsyncSession = Depends(get_session),
):
    """
    Reinitialise le mot de passe avec un token valide.
    """
    from jose import jwt

    from app.config import settings

    try:
        payload = jwt.decode(request.token, settings.jwt_secret, algorithms=["HS256"])
        if payload.get("type") != "reset":
            raise HTTPException(status_code=400, detail="Token invalide")
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=400, detail="Le lien de reinitialisation a expire (1h)")
    except jwt.JWTError:
        raise HTTPException(status_code=400, detail="Token invalide")

    # Valider le nouveau mot de passe
    _validate_password(request.new_password)

    # Trouver l'utilisateur
    user = await session.get(User, payload["sub"])
    if not user:
        raise HTTPException(status_code=404, detail="Utilisateur introuvable")

    # Mettre a jour le mot de passe
    import bcrypt

    user.hashed_password = bcrypt.hashpw(
        request.new_password.encode("utf-8"),
        bcrypt.gensalt(),
    ).decode("utf-8")

    await session.commit()

    # Audit
    await log_audit(
        session=session,
        user_id=user.id,
        org_id=user.org_id,
        action="password_reset_completed",
        resource="auth",
    )

    return {"message": "Mot de passe reinitialise avec succes."}
