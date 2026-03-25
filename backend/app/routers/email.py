"""
THERESE v2 - Email Router

REST API endpoints for email operations.
Supports Gmail (OAuth) and IMAP/SMTP (Local First).

Phase 1 - Core Native Email (Gmail)
Local First - IMAP/SMTP Provider

Logique metier extraite vers services/email_service.py.
"""

import html
import json
import logging

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.models.database import get_session
from app.models.entities import EmailAccount, EmailMessage
from app.models.schemas_email import (
    ClassifyEmailRequest,
    EmailAccountResponse,
    GenerateResponseRequest,
    ImapSetupRequest,
    ImapTestRequest,
    LabelCreateRequest,
    ModifyMessageRequest,
    OAuthCallbackRequest,
    OAuthInitiateRequest,
    OAuthInitiateResponse,
    SendEmailRequest,
    UpdatePriorityRequest,
)
from app.services.email.provider_factory import (
    get_email_provider,
    list_common_providers,
)
from app.services.email_service import (
    classify_email_message,
    discover_email_oauth_credentials,
    ensure_valid_access_token,
    gather_crm_context,
    gather_thread_context,
    get_gmail_oauth_config,
    get_gmail_service_for_account,
    list_and_enrich_gmail_messages,
    upsert_email_account,
)
from app.services.email_service import (
    get_email_stats as _get_email_stats,
)
from app.services.encryption import decrypt_value, encrypt_value
from app.services.gmail_service import GmailService, format_message_for_storage
from app.services.http_client import get_http_client
from app.services.oauth import get_oauth_service

logger = logging.getLogger(__name__)

router = APIRouter()


# ============================================================
# OAuth Endpoints
# ============================================================


@router.post("/auth/initiate")
async def initiate_oauth(
    request: OAuthInitiateRequest,
) -> OAuthInitiateResponse:
    """Initiate Gmail OAuth flow."""
    oauth_service = get_oauth_service()
    config = get_gmail_oauth_config(request.client_id, request.client_secret)
    flow_data = oauth_service.initiate_flow('gmail', config)
    return OAuthInitiateResponse(**flow_data)


@router.post("/auth/callback")
async def handle_oauth_callback(
    request: OAuthCallbackRequest,
    session: AsyncSession = Depends(get_session),
) -> EmailAccountResponse:
    """Handle OAuth callback - exchanges code for tokens and creates/updates email account."""
    oauth_service = get_oauth_service()
    tokens = await oauth_service.handle_callback(request.state, request.code, request.error)

    if not tokens.get('refresh_token'):
        raise HTTPException(status_code=400, detail="No refresh token received. Please revoke access and try again.")

    # Get user email via Gmail API
    gmail = GmailService(tokens['access_token'])
    profile = await gmail.get_profile()
    email_address = profile['emailAddress']

    account, is_new = await upsert_email_account(session, email_address, tokens)
    logger.info(f"Email account {'created' if is_new else 'updated'}: {email_address}")

    return EmailAccountResponse(
        id=account.id,
        email=account.email,
        provider=account.provider,
        scopes=json.loads(account.scopes),
        created_at=account.created_at,
        last_sync=account.last_sync,
    )


@router.get("/auth/callback-redirect", response_class=HTMLResponse)
async def handle_oauth_redirect(
    request: Request,
    session: AsyncSession = Depends(get_session),
):
    """Handle Google's OAuth GET redirect."""
    code = request.query_params.get("code")
    state = request.query_params.get("state")
    error = request.query_params.get("error")

    if error:
        if error == "access_denied":
            error_detail = """
            <p>Google a refuse l'acces a THERESE. Causes probables :</p>
            <ul style="text-align:left;color:#B6C7DA;margin:1rem 0;padding-left:1.5rem;line-height:1.8">
              <li><strong>App en mode Test</strong> : ton adresse email n'est pas dans la liste des utilisateurs de test.<br>
                  -> Google Cloud Console -> API &amp; Services -> Ecran de consentement OAuth -> Utilisateurs de test -> Ajouter ton adresse.</li>
              <li><strong>APIs non activees</strong> : Gmail API et/ou Google Calendar API ne sont pas activees dans ton projet.<br>
                  -> Bibliotheque -> chercher "Gmail API" -> Activer. Meme chose pour "Google Calendar API".</li>
              <li><strong>Client OAuth revoque</strong> : les identifiants ont change ou l'app a ete supprimee.</li>
            </ul>
            <p style="font-size:0.85rem;color:#6B7BA4">Erreur Google : <code>{}</code></p>
            """.format(html.escape(error))
        else:
            error_detail = f"<p>{html.escape(error)}</p>"
        return HTMLResponse(content=f"""
        <!DOCTYPE html>
        <html><head><title>THERESE - Erreur OAuth</title>
        <style>body{{background:#0B1226;color:#E6EDF7;font-family:system-ui;display:flex;align-items:center;justify-content:center;height:100vh;margin:0}}
        .card{{padding:2rem;border:1px solid #22D3EE33;border-radius:1rem;max-width:500px}}
        h1{{color:#E11D8D;font-size:1.5rem}}p{{color:#B6C7DA;margin:1rem 0}}
        strong{{color:#E6EDF7}}code{{color:#22D3EE;font-size:0.8rem}}</style></head>
        <body><div class="card"><h1>Erreur d'autorisation</h1>{error_detail}<p>Tu peux fermer cette fenetre et reessayer.</p></div></body></html>
        """, status_code=400)

    if not code or not state:
        return HTMLResponse(content="""
        <!DOCTYPE html>
        <html><head><title>THERESE - Erreur</title>
        <style>body{background:#0B1226;color:#E6EDF7;font-family:system-ui;display:flex;align-items:center;justify-content:center;height:100vh;margin:0}
        .card{text-align:center;padding:2rem;border:1px solid #22D3EE33;border-radius:1rem;max-width:400px}
        h1{color:#E11D8D;font-size:1.5rem}p{color:#B6C7DA}</style></head>
        <body><div class="card"><h1>Parametres manquants</h1><p>Code ou state manquant dans la reponse Google.</p></div></body></html>
        """, status_code=400)

    try:
        oauth_service = get_oauth_service()
        tokens = await oauth_service.handle_callback(state, code, None)

        if not tokens.get('refresh_token'):
            return HTMLResponse(content="""
            <!DOCTYPE html>
            <html><head><title>THERESE - Erreur</title>
            <style>body{background:#0B1226;color:#E6EDF7;font-family:system-ui;display:flex;align-items:center;justify-content:center;height:100vh;margin:0}
            .card{text-align:center;padding:2rem;border:1px solid #22D3EE33;border-radius:1rem;max-width:400px}
            h1{color:#E11D8D;font-size:1.5rem}p{color:#B6C7DA}</style></head>
            <body><div class="card"><h1>Pas de refresh token</h1><p>Revoque l'acces THERESE dans tes parametres Google et reessaye.</p></div></body></html>
            """, status_code=400)

        gmail = GmailService(tokens['access_token'])
        profile = await gmail.get_profile()
        email_address = profile['emailAddress']

        account, is_new = await upsert_email_account(session, email_address, tokens)
        logger.info(f"Email account {'created' if is_new else 'updated'} via redirect: {email_address}")

        return HTMLResponse(content=f"""
        <!DOCTYPE html>
        <html><head><title>THERESE - Connexion reussie</title>
        <style>body{{background:#0B1226;color:#E6EDF7;font-family:system-ui;display:flex;align-items:center;justify-content:center;height:100vh;margin:0}}
        .card{{text-align:center;padding:2rem;border:1px solid #22D3EE33;border-radius:1rem;max-width:400px}}
        h1{{color:#22D3EE;font-size:1.5rem}}p{{color:#B6C7DA;margin:1rem 0}}
        .email{{color:#22D3EE;font-weight:600}}</style></head>
        <body><div class="card"><h1>Connexion reussie !</h1><p>Le compte <span class="email">{html.escape(email_address)}</span> est connecte a THERESE.</p><p>Tu peux fermer cette fenetre.</p></div></body></html>
        """)
    except (ValueError, OSError, RuntimeError, httpx.HTTPError) as e:
        logger.error(f"OAuth redirect callback failed: {e}")
        return HTMLResponse(content=f"""
        <!DOCTYPE html>
        <html><head><title>THERESE - Erreur</title>
        <style>body{{background:#0B1226;color:#E6EDF7;font-family:system-ui;display:flex;align-items:center;justify-content:center;height:100vh;margin:0}}
        .card{{text-align:center;padding:2rem;border:1px solid #22D3EE33;border-radius:1rem;max-width:400px}}
        h1{{color:#E11D8D;font-size:1.5rem}}p{{color:#B6C7DA}}</style></head>
        <body><div class="card"><h1>Erreur</h1><p>{html.escape(str(e))}</p><p>Tu peux fermer cette fenetre et reessayer.</p></div></body></html>
        """, status_code=500)


@router.post("/auth/reauthorize/{account_id}")
async def reauthorize_account(
    account_id: str,
    session: AsyncSession = Depends(get_session),
) -> OAuthInitiateResponse:
    """Re-authorize an existing account with expired/revoked token."""
    account = await session.get(EmailAccount, account_id)
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")

    client_id, client_secret = await discover_email_oauth_credentials(account)

    if not client_id or not client_secret:
        raise HTTPException(status_code=400, detail="Aucun identifiant OAuth trouve. Reconfigure le compte via le wizard.")

    oauth_service = get_oauth_service()
    config = get_gmail_oauth_config(client_id, client_secret)
    flow_data = oauth_service.initiate_flow('gmail', config)

    logger.info(f"Re-authorization initiated for {account.email}")
    return OAuthInitiateResponse(**flow_data)


@router.get("/auth/status")
async def get_auth_status(
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Get OAuth connection status."""
    statement = select(EmailAccount)
    result = await session.execute(statement)
    accounts = result.scalars().all()

    return {
        'connected': len(accounts) > 0,
        'accounts': [
            {
                'id': acc.id,
                'email': acc.email,
                'provider': acc.provider,
                'last_sync': acc.last_sync.isoformat() if acc.last_sync else None,
                'updated_at': acc.updated_at.isoformat() if getattr(acc, 'updated_at', None) else None,
            }
            for acc in accounts
        ],
    }


@router.post("/auth/update-credentials/{account_id}")
async def update_oauth_credentials(
    account_id: str,
    request: OAuthInitiateRequest,
    session: AsyncSession = Depends(get_session),
):
    """Update OAuth credentials for an existing account."""
    account = await session.get(EmailAccount, account_id)
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")

    account.client_id = encrypt_value(request.client_id)
    account.client_secret = encrypt_value(request.client_secret)
    from app.services.email_service import _utcnow
    account.updated_at = _utcnow()
    session.add(account)
    await session.commit()

    try:
        await ensure_valid_access_token(account, session)
        return {"status": "ok", "message": "Credentials updated and token refreshed", "email": account.email}
    except HTTPException:
        return {"status": "credentials_saved", "message": "Credentials saved but token refresh failed. You may need to re-authorize.", "email": account.email}


@router.delete("/auth/disconnect/{account_id}")
async def disconnect_account(
    account_id: str,
    session: AsyncSession = Depends(get_session),
):
    """Disconnect email account."""
    account = await session.get(EmailAccount, account_id)
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")

    # Revoke OAuth token
    if account.provider == "gmail" and account.access_token:
        try:
            access_token = decrypt_value(account.access_token)
            client = await get_http_client()
            revoke_response = await client.post(
                "https://oauth2.googleapis.com/revoke",
                params={"token": access_token},
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                timeout=10.0,
            )
            if revoke_response.status_code == 200:
                logger.info(f"OAuth token revoked for {account.email}")
            else:
                logger.warning(f"OAuth revocation returned {revoke_response.status_code} for {account.email}")
        except (httpx.HTTPError, OSError, ValueError) as e:
            logger.warning(f"Failed to revoke OAuth token for {account.email}: {e}")

    # Delete messages
    statement = select(EmailMessage).where(EmailMessage.account_id == account_id)
    result = await session.execute(statement)
    messages = result.scalars().all()
    for msg in messages:
        await session.delete(msg)

    await session.delete(account)
    await session.commit()

    logger.info(f"Disconnected email account: {account.email}")
    return {"deleted": True, "account_id": account_id}


# ============================================================
# IMAP/SMTP Endpoints (Local First)
# ============================================================


@router.post("/auth/imap-setup")
async def setup_imap_account(
    request: ImapSetupRequest,
    session: AsyncSession = Depends(get_session),
) -> EmailAccountResponse:
    """Configure un compte IMAP/SMTP."""
    statement = select(EmailAccount).where(EmailAccount.email == request.email)
    result = await session.execute(statement)
    existing = result.scalar_one_or_none()

    if existing:
        existing.provider = "imap"
        existing.imap_host = request.imap_host
        existing.imap_port = request.imap_port
        existing.imap_username = request.email
        existing.imap_password = encrypt_value(request.password)
        existing.smtp_host = request.smtp_host
        existing.smtp_port = request.smtp_port
        existing.smtp_use_tls = request.smtp_use_tls
        from app.services.email_service import _utcnow
        existing.updated_at = _utcnow()
        session.add(existing)
        await session.commit()
        await session.refresh(existing)
        account = existing
    else:
        account = EmailAccount(
            email=request.email,
            provider="imap",
            imap_host=request.imap_host,
            imap_port=request.imap_port,
            imap_username=request.email,
            imap_password=encrypt_value(request.password),
            smtp_host=request.smtp_host,
            smtp_port=request.smtp_port,
            smtp_use_tls=request.smtp_use_tls,
        )
        session.add(account)
        await session.commit()
        await session.refresh(account)

    logger.info(f"IMAP account {'updated' if existing else 'created'}: {request.email}")

    return EmailAccountResponse(
        id=account.id,
        email=account.email,
        provider=account.provider,
        scopes=[],
        created_at=account.created_at,
        last_sync=account.last_sync,
    )


@router.post("/auth/test-connection")
async def test_email_connection(
    request: ImapTestRequest,
) -> dict:
    """Teste la connexion IMAP/SMTP."""
    try:
        provider = get_email_provider(
            provider_type="imap",
            email_address=request.email,
            password=request.password,
            imap_host=request.imap_host,
            imap_port=request.imap_port,
            smtp_host=request.smtp_host,
            smtp_port=request.smtp_port,
            smtp_use_tls=request.smtp_use_tls,
        )
        result = await provider.test_connection()
        return result
    except (OSError, ValueError, RuntimeError) as e:
        logger.error(f"Connection test failed: {e}")
        return {"success": False, "message": f"Echec de connexion: {e!s}"}


@router.get("/providers")
async def list_email_providers() -> list[dict]:
    """Liste les providers email preconfigures (IMAP/SMTP)."""
    return list_common_providers()


# ============================================================
# Messages Endpoints
# ============================================================


@router.get("/messages")
async def list_messages(
    account_id: str = Query(...),
    max_results: int = Query(50, ge=1, le=500),
    page_token: str | None = Query(None),
    query: str | None = Query(None),
    label_ids: str | None = Query(None),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """List messages from email account (Gmail or IMAP)."""
    account = await session.get(EmailAccount, account_id)
    if not account:
        raise HTTPException(status_code=404, detail="Email account not found")

    if account.provider == "imap":
        return await _list_messages_imap(account, max_results, query)
    else:
        return await _list_messages_gmail(account_id, session, max_results, page_token, query, label_ids)


async def _list_messages_gmail(
    account_id: str,
    session: AsyncSession,
    max_results: int,
    page_token: str | None,
    query: str | None,
    label_ids: str | None,
) -> dict:
    """List messages via Gmail API."""
    gmail = await get_gmail_service_for_account(account_id, session)
    label_ids_list = label_ids.split(',') if label_ids else None
    return await list_and_enrich_gmail_messages(gmail, max_results, page_token, query, label_ids_list)


async def _list_messages_imap(
    account: EmailAccount,
    max_results: int,
    query: str | None,
) -> dict:
    """List messages via IMAP provider."""
    provider = get_email_provider(
        provider_type="imap",
        email_address=account.email,
        password=decrypt_value(account.imap_password),
        imap_host=account.imap_host,
        imap_port=account.imap_port,
        smtp_host=account.smtp_host,
        smtp_port=account.smtp_port,
        smtp_use_tls=account.smtp_use_tls,
    )

    messages = await provider.list_messages(max_results=max_results, query=query)

    enriched = []
    for msg in messages:
        enriched.append({
            'id': msg.id,
            'threadId': msg.thread_id or msg.id,
            'snippet': msg.snippet or '',
            'subject': msg.subject or '(Pas de sujet)',
            'from': f"{msg.from_name or ''} <{msg.from_email}>".strip(),
            'date': msg.date.isoformat() if msg.date else '',
            'labelIds': msg.labels or [],
        })

    return {
        'messages': enriched,
        'nextPageToken': None,
        'resultSizeEstimate': len(enriched),
    }


@router.get("/messages/stats")
async def get_email_stats(
    account_id: str = Query(...),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Recupere les statistiques d'emails par priorite."""
    return await _get_email_stats(session, account_id)


@router.get("/messages/{message_id}")
async def get_message(
    message_id: str,
    account_id: str = Query(...),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Get message details."""
    cached = await session.get(EmailMessage, message_id)
    if cached and cached.account_id == account_id and (cached.body_plain or cached.body_html):
        return {
            'id': cached.id,
            'thread_id': cached.thread_id,
            'subject': cached.subject,
            'from_email': cached.from_email,
            'from_name': cached.from_name,
            'to_emails': json.loads(cached.to_emails),
            'date': cached.date.isoformat(),
            'labels': json.loads(cached.labels),
            'is_read': cached.is_read,
            'is_starred': cached.is_starred,
            'body_plain': cached.body_plain,
            'body_html': cached.body_html,
        }

    gmail = await get_gmail_service_for_account(account_id, session)
    message = await gmail.get_message(message_id)

    formatted = format_message_for_storage(message)
    formatted['account_id'] = account_id
    db_message = EmailMessage(**formatted)
    session.add(db_message)
    await session.commit()

    return message


@router.post("/messages")
async def send_email(
    request: SendEmailRequest,
    account_id: str = Query(...),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Send an email (Gmail or IMAP/SMTP)."""
    account = await session.get(EmailAccount, account_id)
    if not account:
        raise HTTPException(status_code=404, detail="Email account not found")

    if account.provider == "imap":
        provider = get_email_provider(
            provider_type="imap",
            email_address=account.email,
            password=decrypt_value(account.imap_password),
            imap_host=account.imap_host,
            imap_port=account.imap_port,
            smtp_host=account.smtp_host,
            smtp_port=account.smtp_port,
            smtp_use_tls=account.smtp_use_tls,
        )
        from app.services.email.base_provider import SendEmailRequest as ProviderSendRequest
        send_req = ProviderSendRequest(
            to=request.to,
            subject=request.subject,
            body=request.body,
            cc=request.cc or [],
            bcc=request.bcc or [],
            is_html=request.html,
        )
        message_id = await provider.send_message(send_req)
        return {"id": message_id, "labelIds": ["SENT"]}
    else:
        gmail = await get_gmail_service_for_account(account_id, session)
        result = await gmail.send_message(
            to=request.to, subject=request.subject, body=request.body,
            cc=request.cc, bcc=request.bcc, html=request.html,
        )
        return result


@router.post("/messages/draft")
async def create_draft(
    request: SendEmailRequest,
    account_id: str = Query(...),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Create a draft email."""
    gmail = await get_gmail_service_for_account(account_id, session)
    return await gmail.create_draft(
        to=request.to, subject=request.subject, body=request.body,
        cc=request.cc, bcc=request.bcc, html=request.html,
    )


@router.put("/messages/{message_id}")
async def modify_message(
    message_id: str,
    request: ModifyMessageRequest,
    account_id: str = Query(...),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Modify message labels."""
    gmail = await get_gmail_service_for_account(account_id, session)
    result = await gmail.modify_message(
        message_id=message_id,
        add_label_ids=request.add_label_ids,
        remove_label_ids=request.remove_label_ids,
    )

    # Update cache
    cached = await session.get(EmailMessage, message_id)
    if cached:
        labels = json.loads(cached.labels)
        if request.add_label_ids:
            labels.extend(request.add_label_ids)
        if request.remove_label_ids:
            labels = [lbl for lbl in labels if lbl not in request.remove_label_ids]
        cached.labels = json.dumps(list(set(labels)))
        cached.is_read = 'UNREAD' not in labels
        cached.is_starred = 'STARRED' in labels
        session.add(cached)
        await session.commit()

    return result


@router.delete("/messages/{message_id}")
async def delete_message(
    message_id: str,
    account_id: str = Query(...),
    permanent: bool = Query(False),
    session: AsyncSession = Depends(get_session),
):
    """Delete message (trash or permanent)."""
    gmail = await get_gmail_service_for_account(account_id, session)

    if permanent:
        await gmail.delete_message(message_id)
    else:
        await gmail.trash_message(message_id)

    cached = await session.get(EmailMessage, message_id)
    if cached:
        await session.delete(cached)
        await session.commit()

    return {"deleted": True, "message_id": message_id, "permanent": permanent}


# ============================================================
# Labels Endpoints
# ============================================================


@router.get("/labels")
async def list_labels(
    account_id: str = Query(...),
    session: AsyncSession = Depends(get_session),
) -> list[dict]:
    """List email labels/folders."""
    account = await session.get(EmailAccount, account_id)
    if not account:
        raise HTTPException(status_code=404, detail="Email account not found")

    if account.provider == "imap":
        provider = get_email_provider(
            provider_type="imap",
            email_address=account.email,
            password=decrypt_value(account.imap_password),
            imap_host=account.imap_host,
            imap_port=account.imap_port,
            smtp_host=account.smtp_host,
            smtp_port=account.smtp_port,
            smtp_use_tls=account.smtp_use_tls,
        )
        folders = await provider.list_folders()
        return [
            {"id": f.id, "name": f.name, "type": f.type, "messagesTotal": f.messages_total, "messagesUnread": f.messages_unread}
            for f in folders
        ]
    else:
        gmail = await get_gmail_service_for_account(account_id, session)
        return await gmail.list_labels()


@router.post("/labels")
async def create_label(
    request: LabelCreateRequest,
    account_id: str = Query(...),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Create a new label."""
    gmail = await get_gmail_service_for_account(account_id, session)
    return await gmail.create_label(request.name)


@router.put("/labels/{label_id}")
async def update_label(
    label_id: str,
    request: LabelCreateRequest,
    account_id: str = Query(...),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Update label name."""
    gmail = await get_gmail_service_for_account(account_id, session)
    return await gmail.update_label(label_id, request.name)


@router.delete("/labels/{label_id}")
async def delete_label(
    label_id: str,
    account_id: str = Query(...),
    session: AsyncSession = Depends(get_session),
):
    """Delete a label."""
    gmail = await get_gmail_service_for_account(account_id, session)
    await gmail.delete_label(label_id)
    return {"deleted": True, "label_id": label_id}


# ============================================================
# Smart Email Features Endpoints
# ============================================================


@router.post("/messages/{message_id}/classify")
async def classify_email(
    message_id: str,
    request: ClassifyEmailRequest,
    account_id: str = Query(...),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Classifie un email par priorite (Rouge/Orange/Vert)."""
    message = await session.get(EmailMessage, message_id)

    if not message:
        gmail = await get_gmail_service_for_account(account_id, session)
        gmail_msg = await gmail.get_message(message_id)
        formatted = format_message_for_storage(gmail_msg)
        formatted['account_id'] = account_id
        message = EmailMessage(**formatted)
        session.add(message)
        await session.commit()
        await session.refresh(message)

    if message.account_id != account_id:
        raise HTTPException(status_code=404, detail="Message not found")

    return await classify_email_message(session, message, account_id, force_reclassify=request.force_reclassify)


@router.post("/messages/{message_id}/generate-response")
async def generate_email_response(
    message_id: str,
    request: GenerateResponseRequest,
    account_id: str = Query(...),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Genere une proposition de reponse intelligente via LLM."""
    from app.services.email_response_generator import EmailResponseGenerator

    message = await session.get(EmailMessage, message_id)
    if not message or message.account_id != account_id:
        raise HTTPException(status_code=404, detail="Message not found")

    contact_context = await gather_crm_context(message)
    thread_context = await gather_thread_context(session, message)

    response_text = await EmailResponseGenerator.generate_response(
        subject=message.subject or '',
        from_name=message.from_name or message.from_email,
        from_email=message.from_email,
        body=message.body_plain or message.snippet or '',
        tone=request.tone,
        length=request.length,
        contact_context=contact_context,
        thread_context=thread_context,
    )

    return {
        'message_id': message_id,
        'draft': response_text,
        'tone': request.tone,
        'length': request.length,
    }


@router.patch("/messages/{message_id}/priority")
async def update_message_priority(
    message_id: str,
    request: UpdatePriorityRequest,
    account_id: str = Query(...),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Change manuellement la priorite d'un email."""
    if request.priority not in ['high', 'medium', 'low']:
        raise HTTPException(status_code=400, detail="Invalid priority. Must be 'high', 'medium', or 'low'.")

    message = await session.get(EmailMessage, message_id)
    if not message or message.account_id != account_id:
        raise HTTPException(status_code=404, detail="Message not found")

    message.priority = request.priority
    message.priority_reason = "Defini manuellement par l'utilisateur"
    if not message.priority_score:
        score_map = {'high': 75, 'medium': 40, 'low': 10}
        message.priority_score = score_map[request.priority]

    session.add(message)
    await session.commit()

    return {
        'message_id': message_id,
        'priority': message.priority,
        'score': message.priority_score,
        'reason': message.priority_reason,
    }
