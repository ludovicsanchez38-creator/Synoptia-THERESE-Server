"""
THERESE v2 - Email Service

Logique metier extraite du router email.
Gere : refresh token OAuth, creation/MAJ de comptes email,
enrichissement de messages Gmail, classification avec contexte CRM,
generation de reponses avec contexte thread/CRM, statistiques email.
"""

import asyncio
import json
import logging
from datetime import datetime, timedelta, timezone

import httpx
from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.models.entities import EmailAccount, EmailMessage
from app.services.encryption import decrypt_value, encrypt_value, is_value_encrypted
from app.services.gmail_service import GmailService
from app.services.oauth import (
    GOOGLE_ALL_SCOPES,
    GOOGLE_AUTH_URL,
    GOOGLE_TOKEN_URL,
    RUNTIME_PORT,
    OAuthConfig,
    get_oauth_service,
)

logger = logging.getLogger(__name__)


def _utcnow() -> datetime:
    """UTC now as naive datetime (compatible SQLite)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def get_gmail_oauth_config(
    client_id: str,
    client_secret: str,
) -> OAuthConfig:
    """Get Google OAuth configuration (Gmail + Calendar scopes)."""
    return OAuthConfig(
        client_id=client_id,
        client_secret=client_secret,
        auth_url=GOOGLE_AUTH_URL,
        token_url=GOOGLE_TOKEN_URL,
        scopes=GOOGLE_ALL_SCOPES,
        redirect_uri=f"http://localhost:{RUNTIME_PORT}/api/email/auth/callback-redirect",
    )


# =============================================================================
# Token Refresh
# =============================================================================


async def ensure_valid_access_token(
    account: EmailAccount,
    session: AsyncSession,
) -> str:
    """
    Ensure the access token is valid, refreshing if expired.

    Used by both email and calendar routers.

    Returns:
        Valid (decrypted) access token.

    Raises:
        HTTPException(401): si les credentials sont introuvables ou le refresh echoue.
    """
    access_token = decrypt_value(account.access_token)

    # Check if token expired
    if account.token_expiry and _utcnow() >= account.token_expiry:
        logger.info(f"Access token expired for {account.email}, refreshing...")
        refresh_token = decrypt_value(account.refresh_token)

        try:
            client_id = None
            client_secret = None

            # 1. Try stored credentials on the account
            if account.client_id and account.client_secret:
                client_id = decrypt_value(account.client_id)
                client_secret = decrypt_value(account.client_secret)
                logger.debug("Using stored OAuth credentials from account")

            # 2. Fallback: Try MCP Google Workspace server
            if not client_id or not client_secret:
                from app.services.mcp_service import get_mcp_service

                mcp_service = get_mcp_service()

                for _server_id, server in mcp_service.servers.items():
                    if 'google' in server.name.lower() and 'workspace' in server.name.lower():
                        env = server.env or {}
                        cid = env.get('GOOGLE_OAUTH_CLIENT_ID', '')
                        csecret = env.get('GOOGLE_OAUTH_CLIENT_SECRET', '')

                        if is_value_encrypted(cid):
                            cid = decrypt_value(cid)
                        if is_value_encrypted(csecret):
                            csecret = decrypt_value(csecret)

                        if cid and csecret:
                            client_id = cid
                            client_secret = csecret
                            break

            if not client_id or not client_secret:
                raise HTTPException(
                    status_code=401,
                    detail="OAuth credentials not found. Please reconnect your account."
                )

            # Refresh token using OAuth service
            oauth_service = get_oauth_service()
            config = get_gmail_oauth_config(client_id, client_secret)

            new_tokens = await oauth_service.refresh_access_token(
                refresh_token,
                config,
            )

            # Update account with new tokens
            account.access_token = encrypt_value(new_tokens['access_token'])
            account.token_expiry = _utcnow() + timedelta(seconds=new_tokens['expires_in'])
            account.updated_at = _utcnow()
            # Rotation du refresh_token (Google peut en emettre un nouveau)
            if new_tokens.get('refresh_token'):
                account.refresh_token = encrypt_value(new_tokens['refresh_token'])
                logger.info(f"Refresh token renouvele pour {account.email}")
            session.add(account)
            await session.commit()

            logger.info(f"Access token refreshed for {account.email}")
            access_token = new_tokens['access_token']

        except HTTPException:
            raise
        except (httpx.HTTPError, ValueError, OSError) as e:
            logger.error(f"Failed to refresh token: {e}")
            raise HTTPException(
                status_code=401,
                detail="Access token expired. Please reconnect your account."
            )

    return access_token


async def get_gmail_service_for_account(
    account_id: str,
    session: AsyncSession,
) -> GmailService:
    """
    Get authenticated Gmail service for account.

    Handles token refresh if needed.
    """
    account = await session.get(EmailAccount, account_id)
    if not account:
        raise HTTPException(status_code=404, detail="Email account not found")

    access_token = await ensure_valid_access_token(account, session)

    return GmailService(access_token)


# =============================================================================
# Account Create / Update (shared by callback + redirect)
# =============================================================================


async def upsert_email_account(
    session: AsyncSession,
    email_address: str,
    tokens: dict,
) -> tuple[EmailAccount, bool]:
    """
    Cree ou met a jour un EmailAccount apres un callback OAuth.

    Returns:
        (account, is_new) - l'account et un boolean indiquant si c'est une creation.
    """
    statement = select(EmailAccount).where(EmailAccount.email == email_address)
    result = await session.execute(statement)
    existing = result.scalar_one_or_none()

    if existing:
        existing.access_token = encrypt_value(tokens['access_token'])
        existing.refresh_token = encrypt_value(tokens['refresh_token'])
        existing.token_expiry = _utcnow() + timedelta(seconds=tokens['expires_in'])
        existing.scopes = json.dumps(tokens['scopes'])
        if tokens.get('client_id'):
            existing.client_id = encrypt_value(tokens['client_id'])
        if tokens.get('client_secret'):
            existing.client_secret = encrypt_value(tokens['client_secret'])
        existing.updated_at = _utcnow()
        session.add(existing)
        await session.commit()
        await session.refresh(existing)
        return existing, False
    else:
        account = EmailAccount(
            email=email_address,
            access_token=encrypt_value(tokens['access_token']),
            refresh_token=encrypt_value(tokens['refresh_token']),
            token_expiry=_utcnow() + timedelta(seconds=tokens['expires_in']),
            scopes=json.dumps(tokens['scopes']),
            client_id=encrypt_value(tokens['client_id']) if tokens.get('client_id') else None,
            client_secret=encrypt_value(tokens['client_secret']) if tokens.get('client_secret') else None,
        )
        session.add(account)
        await session.commit()
        await session.refresh(account)
        return account, True


# =============================================================================
# Gmail Message Enrichment
# =============================================================================


async def list_and_enrich_gmail_messages(
    gmail: GmailService,
    max_results: int,
    page_token: str | None,
    query: str | None,
    label_ids_list: list[str] | None,
) -> dict:
    """
    Liste et enrichit les messages Gmail avec metadata (subject, from, date, etc.).

    Concurrence limitee a 5 requetes simultanees pour eviter le rate limit Gmail API.

    Returns:
        Dict avec messages, nextPageToken, resultSizeEstimate.
    """
    result = await gmail.list_messages(
        max_results=max_results,
        page_token=page_token,
        query=query,
        label_ids=label_ids_list,
    )

    sem = asyncio.Semaphore(5)

    async def _enrich_one(msg: dict) -> dict:
        async with sem:
            try:
                msg_detail = await gmail.get_message(msg['id'], format='metadata')
                headers = {h['name']: h['value'] for h in msg_detail.get('payload', {}).get('headers', [])}
                label_ids_msg = msg_detail.get('labelIds', [])

                return {
                    'id': msg['id'],
                    'threadId': msg.get('threadId'),
                    'snippet': msg_detail.get('snippet', ''),
                    'subject': headers.get('Subject', '(No subject)'),
                    'from': headers.get('From', ''),
                    'date': headers.get('Date', ''),
                    'labelIds': label_ids_msg,
                    'is_read': 'UNREAD' not in label_ids_msg,
                    'is_starred': 'STARRED' in label_ids_msg,
                }
            except (httpx.HTTPError, OSError, KeyError, ValueError) as e:
                logger.error(f"Failed to get message {msg['id']}: {e}")
                return {
                    'id': msg['id'],
                    'threadId': msg.get('threadId'),
                    'error': str(e),
                }

    raw_messages = result.get('messages', [])
    enriched_messages = await asyncio.gather(
        *(_enrich_one(msg) for msg in raw_messages)
    ) if raw_messages else []

    error_count = sum(1 for m in enriched_messages if m.get('error'))
    if error_count:
        logger.warning(f"Email enrichment: {len(enriched_messages) - error_count}/{len(enriched_messages)} OK, {error_count} errors")

    return {
        'messages': list(enriched_messages),
        'nextPageToken': result.get('nextPageToken'),
        'resultSizeEstimate': result.get('resultSizeEstimate'),
    }


# =============================================================================
# Email Classification with CRM context
# =============================================================================


async def classify_email_message(
    session: AsyncSession,
    message: EmailMessage,
    account_id: str,
    force_reclassify: bool = False,
) -> dict:
    """
    Classifie un email par priorite (Rouge/Orange/Vert) avec contexte CRM.

    Si deja classifie et force_reclassify=False, retourne le cache.

    Returns:
        Dict avec message_id, priority, category, score, reason, signals, cached.
    """
    from app.services.email_classifier_v2 import EmailClassifierV2

    # Skip if already classified (unless force)
    if message.priority and not force_reclassify:
        return {
            'message_id': message.id,
            'priority': message.priority,
            'score': message.priority_score,
            'reason': message.priority_reason,
            'cached': True,
        }

    # Get CRM contact score if exists
    contact_score = None
    try:
        from app.services.qdrant import get_qdrant_service
        qdrant = get_qdrant_service()
        results = qdrant.search(
            query=f"{message.from_name} {message.from_email}",
            entity_type='contact',
            limit=1,
        )
        if results:
            contact_score = results[0].payload.get('score', None)
    except (RuntimeError, OSError, ValueError) as e:
        logger.warning(f"Failed to get CRM score for {message.from_email}: {e}")

    # Classify
    labels_list = json.loads(message.labels) if message.labels else []
    result = EmailClassifierV2.classify(
        subject=message.subject or '',
        from_email=message.from_email,
        from_name=message.from_name or '',
        snippet=message.snippet or '',
        labels=labels_list,
        has_attachments=message.has_attachments,
        date=message.date,
        contact_score=contact_score,
    )

    # Update DB
    message.priority = result.priority
    message.priority_score = result.score
    message.priority_reason = result.reason
    message.category = result.category
    session.add(message)
    await session.commit()

    return {
        'message_id': message.id,
        'priority': result.priority,
        'category': result.category,
        'score': result.score,
        'reason': result.reason,
        'signals': result.signals,
        'cached': False,
    }


# =============================================================================
# Response Generation with CRM/Thread context
# =============================================================================


async def gather_crm_context(message: EmailMessage) -> str | None:
    """
    Recupere le contexte CRM pour un email (nom, entreprise, score, etc.).

    Returns:
        Texte de contexte CRM ou None si introuvable.
    """
    try:
        from app.services.qdrant import get_qdrant_service
        qdrant = get_qdrant_service()
        results = qdrant.search(
            query=f"{message.from_name} {message.from_email}",
            entity_type='contact',
            limit=1,
        )
        if results:
            payload = results[0].payload
            return f"""Contact CRM :
- Nom : {payload.get('name', 'N/A')}
- Entreprise : {payload.get('company', 'N/A')}
- Email : {payload.get('email', 'N/A')}
- Telephone : {payload.get('phone', 'N/A')}
- Score : {payload.get('score', 'N/A')}/100
- Tags : {payload.get('tags', 'N/A')}
- Notes : {payload.get('notes', 'N/A')}"""
    except (RuntimeError, OSError, ValueError) as e:
        logger.warning(f"Failed to get CRM context for {message.from_email}: {e}")

    return None


async def gather_thread_context(
    session: AsyncSession,
    message: EmailMessage,
) -> str | None:
    """
    Recupere le contexte du thread (emails precedents).

    Returns:
        Texte de contexte thread ou None si pas d'historique.
    """
    try:
        statement = select(EmailMessage).where(
            EmailMessage.thread_id == message.thread_id,
            EmailMessage.id != message.id,
        ).order_by(EmailMessage.date.desc()).limit(3)
        result = await session.execute(statement)
        thread_messages = result.scalars().all()

        if thread_messages:
            thread_lines = []
            for tm in thread_messages:
                thread_lines.append(f"[{tm.date.strftime('%Y-%m-%d %H:%M')}] De: {tm.from_name or tm.from_email}")
                thread_lines.append(f"Sujet: {tm.subject}")
                thread_lines.append(f"{tm.snippet or tm.body_plain[:200]}")
                thread_lines.append("---")
            return "\n".join(thread_lines)
    except (OSError, ValueError, RuntimeError) as e:
        logger.warning(f"Failed to get thread context for {message.id}: {e}")

    return None


# =============================================================================
# Email Stats
# =============================================================================


async def get_email_stats(
    session: AsyncSession,
    account_id: str,
) -> dict:
    """
    Calcule les statistiques d'emails par priorite.

    Returns:
        Dict avec high, medium, low, total_unread, total.
    """
    # High priority (unread)
    statement_high = select(func.count(EmailMessage.id)).where(
        EmailMessage.account_id == account_id,
        EmailMessage.priority == 'high',
        EmailMessage.is_read == False,  # noqa: E712
    )
    result_high = await session.execute(statement_high)
    high_count = result_high.scalar_one()

    # Medium priority (unread)
    statement_medium = select(func.count(EmailMessage.id)).where(
        EmailMessage.account_id == account_id,
        EmailMessage.priority == 'medium',
        EmailMessage.is_read == False,  # noqa: E712
    )
    result_medium = await session.execute(statement_medium)
    medium_count = result_medium.scalar_one()

    # Low priority (unread)
    statement_low = select(func.count(EmailMessage.id)).where(
        EmailMessage.account_id == account_id,
        EmailMessage.priority == 'low',
        EmailMessage.is_read == False,  # noqa: E712
    )
    result_low = await session.execute(statement_low)
    low_count = result_low.scalar_one()

    total_unread = high_count + medium_count + low_count

    # Total messages
    statement_total = select(func.count(EmailMessage.id)).where(
        EmailMessage.account_id == account_id,
    )
    result_total = await session.execute(statement_total)
    total_count = result_total.scalar_one()

    return {
        'high': high_count,
        'medium': medium_count,
        'low': low_count,
        'total_unread': total_unread,
        'total': total_count,
    }


# =============================================================================
# Reauthorize - credential discovery for email accounts
# =============================================================================


async def discover_email_oauth_credentials(
    account: EmailAccount,
) -> tuple[str | None, str | None]:
    """
    Recherche les credentials OAuth pour un compte email.

    Ordre de priorite :
    1. Credentials stockees sur le compte
    2. Serveur MCP Google Workspace

    Returns:
        (client_id, client_secret) ou (None, None).
    """
    client_id = None
    client_secret = None

    # 1. Try stored credentials on the account
    if account.client_id and account.client_secret:
        client_id = decrypt_value(account.client_id)
        client_secret = decrypt_value(account.client_secret)

    # 2. Fallback: MCP Google Workspace
    if not client_id or not client_secret:
        try:
            from app.services.mcp_service import get_mcp_service
            mcp_service = get_mcp_service()
            for _server_id, server in mcp_service.servers.items():
                if 'google' in server.name.lower() and 'workspace' in server.name.lower():
                    env = server.env or {}
                    cid = env.get('GOOGLE_OAUTH_CLIENT_ID', '')
                    csecret = env.get('GOOGLE_OAUTH_CLIENT_SECRET', '')
                    if is_value_encrypted(cid):
                        cid = decrypt_value(cid)
                    if is_value_encrypted(csecret):
                        csecret = decrypt_value(csecret)
                    if cid and csecret:
                        client_id = cid
                        client_secret = csecret
                        break
        except (ValueError, OSError, RuntimeError) as e:
            logger.warning(f"Failed to get MCP credentials: {e}")

    return client_id, client_secret
