"""
THERESE v2 - CRM Service

Logique metier extraite du router CRM.
Gere : sync Google Sheets, import direct, pipeline stats,
creation de contacts avec push GSheets, decouverte credentials OAuth.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.services.sheets_service import GoogleSheetsService
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import func, select

from app.models.entities import Activity, Contact, EmailAccount, Preference
from app.services.crm_utils import (
    new_sync_stats,
    upsert_contact,
    upsert_deliverable_from_import,
    upsert_project,
    upsert_task,
)
from app.services.encryption import decrypt_value, encrypt_value
from app.services.scoring import update_contact_score

logger = logging.getLogger(__name__)


# =============================================================================
# Helpers
# =============================================================================


def _sanitize_row(row: dict) -> dict:
    """Sanitize all string values in an import row (SEC-017)."""
    from app.services.crm_import import _sanitize_field

    sanitized = {}
    for key, value in row.items():
        sanitized[key] = _sanitize_field(value, key.lower()) if isinstance(value, str) else value
    return sanitized


# =============================================================================
# Pipeline & Scoring
# =============================================================================


async def change_contact_stage(
    session: AsyncSession,
    contact: Contact,
    new_stage: str,
) -> Contact:
    """
    Change le stage d'un contact, cree une activite et recalcule le score.

    Returns:
        Le contact mis a jour (non commite - l'appelant doit commit).
    """
    old_stage = contact.stage

    contact.stage = new_stage
    contact.updated_at = datetime.utcnow()
    contact.last_interaction = datetime.utcnow()
    session.add(contact)

    # Creer une activite
    activity = Activity(
        contact_id=contact.id,
        type="stage_change",
        title=f"Stage: {old_stage} -> {new_stage}",
        description="Changement de stage dans le pipeline commercial",
        extra_data=f'{{"old_stage": "{old_stage}", "new_stage": "{new_stage}"}}',
    )
    session.add(activity)

    # Recalculer le score
    await update_contact_score(session, contact, reason=f"stage_change_{new_stage}")

    return contact


async def get_pipeline_stats(
    session: AsyncSession,
    user_id: str,
) -> dict:
    """
    Calcule les statistiques du pipeline commercial.

    Returns:
        Dict avec total_contacts et stages (count + avg_score par stage).
    """
    # Compter contacts par stage (scoped)
    stages_count_statement = (
        select(Contact.stage, func.count(Contact.id))
        .where(Contact.user_id == user_id)
        .group_by(Contact.stage)
    )
    result = await session.execute(stages_count_statement)
    stages_count = result.all()

    # Score moyen par stage (scoped)
    stages_avg_score_statement = (
        select(Contact.stage, func.avg(Contact.score))
        .where(Contact.user_id == user_id)
        .group_by(Contact.stage)
    )
    result = await session.execute(stages_avg_score_statement)
    stages_avg_score = result.all()

    # Total contacts (scoped)
    result = await session.execute(
        select(func.count(Contact.id)).where(Contact.user_id == user_id)
    )
    total_contacts = result.scalar_one()

    # Construire la reponse
    stages_data = {}

    for stage, count in stages_count:
        stages_data[stage] = {"count": count}

    for stage, avg_score in stages_avg_score:
        if stage in stages_data:
            stages_data[stage]["avg_score"] = float(avg_score) if avg_score else 0.0

    return {
        "total_contacts": total_contacts,
        "stages": stages_data,
    }


# =============================================================================
# Contact creation with GSheets push
# =============================================================================


async def push_contact_to_sheets(
    session: AsyncSession,
    contact: Contact,
    source: str,
) -> None:
    """
    Tente de pousser un contact vers Google Sheets.

    Ne leve pas d'exception si le push echoue (best effort).
    """
    try:
        result = await session.execute(
            select(Preference).where(Preference.key == "crm_spreadsheet_id")
        )
        spreadsheet_pref = result.scalar_one_or_none()

        result = await session.execute(
            select(Preference).where(Preference.key == "crm_sheets_access_token")
        )
        token_pref = result.scalar_one_or_none()

        if spreadsheet_pref and spreadsheet_pref.value and token_pref and token_pref.value:
            from app.services.sheets_service import GoogleSheetsService

            access_token = decrypt_value(token_pref.value)
            sheets = GoogleSheetsService(access_token=access_token)

            full_name = f"{contact.first_name or ''} {contact.last_name or ''}".strip()
            row_values = [
                contact.id,
                full_name,
                contact.company or "",
                contact.email or "",
                contact.phone or "",
                source,
                contact.stage,
                str(contact.score),
                "",  # Tags
            ]

            await sheets.append_row(spreadsheet_pref.value, "Clients", row_values)
            logger.info("Contact %s pushed to Google Sheets", contact.id)
        else:
            logger.debug("CRM sync not configured, contact created locally only")

    except (OSError, ValueError, RuntimeError) as e:
        # Ne pas bloquer la creation si le push GSheets echoue
        logger.warning("Failed to push contact to Google Sheets: %s", e)


# =============================================================================
# Google OAuth Credential Discovery
# =============================================================================


async def discover_google_credentials(
    session: AsyncSession,
) -> tuple[str | None, str | None]:
    """
    Recherche les credentials Google OAuth dans plusieurs sources.

    Ordre de priorite :
    1. Serveur MCP Google Workspace configure
    2. Preferences stockees
    3. EmailAccount Gmail existant (reutilisation des credentials)

    Returns:
        (client_id, client_secret) ou (None, None) si introuvable.
    """
    client_id = None
    client_secret = None

    # 1. Try MCP Google Workspace server
    try:
        from app.services.mcp_service import get_mcp_service

        mcp_service = get_mcp_service()
        for server in mcp_service.list_servers():
            if server.get("name", "").lower() in ["google-workspace", "google workspace"]:
                env_vars = server.get("env", {})
                cid = env_vars.get("GOOGLE_OAUTH_CLIENT_ID")
                csecret = env_vars.get("GOOGLE_OAUTH_CLIENT_SECRET")

                # Decrypt credentials (they are stored encrypted)
                if cid:
                    try:
                        cid = decrypt_value(cid)
                    except (ValueError, OSError):
                        pass  # May not be encrypted
                if csecret:
                    try:
                        csecret = decrypt_value(csecret)
                    except (ValueError, OSError):
                        pass

                if cid and csecret:
                    client_id = cid
                    client_secret = csecret
                    logger.info("Using Google credentials from MCP server")
                    break
    except (ValueError, OSError, RuntimeError) as e:
        logger.warning("Could not get credentials from MCP: %s", e)

    # 2. Fallback to preferences
    if not client_id or not client_secret:
        result = await session.execute(
            select(Preference).where(Preference.key == "google_client_id")
        )
        client_id_pref = result.scalar_one_or_none()

        result = await session.execute(
            select(Preference).where(Preference.key == "google_client_secret")
        )
        client_secret_pref = result.scalar_one_or_none()

        if client_id_pref and client_secret_pref:
            try:
                client_id = decrypt_value(client_id_pref.value)
                client_secret = decrypt_value(client_secret_pref.value)
                logger.info("Using Google credentials from preferences")
            except (ValueError, OSError):
                pass

    # 3. Fallback: reutiliser les credentials d'un EmailAccount Google existant
    if not client_id or not client_secret:
        try:
            email_result = await session.execute(
                select(EmailAccount).where(
                    EmailAccount.provider == "gmail",
                    EmailAccount.client_id.isnot(None),
                    EmailAccount.client_secret.isnot(None),
                )
            )
            email_account = email_result.scalar_one_or_none()
            if email_account and email_account.client_id and email_account.client_secret:
                client_id = decrypt_value(email_account.client_id)
                client_secret = decrypt_value(email_account.client_secret)
                logger.info("Using Google credentials from EmailAccount")
        except (ValueError, OSError) as e:
            logger.warning("Could not get credentials from EmailAccount: %s", e)

    return client_id, client_secret


# =============================================================================
# Sync Config
# =============================================================================


async def get_sync_config(session: AsyncSession) -> dict:
    """
    Recupere la configuration de synchronisation CRM.

    Returns:
        Dict avec spreadsheet_id, last_sync, has_token, configured.
    """
    result = await session.execute(
        select(Preference).where(Preference.key == "crm_spreadsheet_id")
    )
    spreadsheet_pref = result.scalar_one_or_none()
    spreadsheet_id = spreadsheet_pref.value if spreadsheet_pref else None

    result = await session.execute(
        select(Preference).where(Preference.key == "crm_last_sync")
    )
    last_sync_pref = result.scalar_one_or_none()
    last_sync = last_sync_pref.value if last_sync_pref else None

    result = await session.execute(
        select(Preference).where(Preference.key == "crm_sheets_access_token")
    )
    token_pref = result.scalar_one_or_none()
    has_token = token_pref is not None and bool(token_pref.value)

    return {
        "spreadsheet_id": spreadsheet_id,
        "last_sync": last_sync,
        "has_token": has_token,
        "configured": bool(spreadsheet_id and has_token),
    }


async def upsert_sync_spreadsheet_id(
    session: AsyncSession,
    spreadsheet_id: str,
) -> None:
    """
    Upsert le spreadsheet ID dans les preferences.
    """
    result = await session.execute(
        select(Preference).where(Preference.key == "crm_spreadsheet_id")
    )
    pref = result.scalar_one_or_none()

    if pref:
        pref.value = spreadsheet_id
        pref.updated_at = datetime.utcnow()
    else:
        pref = Preference(
            key="crm_spreadsheet_id",
            value=spreadsheet_id,
            category="crm",
        )
        session.add(pref)

    await session.commit()


async def save_google_credentials(
    session: AsyncSession,
    client_id: str,
    client_secret: str,
) -> None:
    """
    Stocke les credentials Google OAuth (chiffrees) dans les preferences.
    """
    for pref_key, pref_value in [
        ("google_client_id", client_id),
        ("google_client_secret", client_secret),
    ]:
        result = await session.execute(
            select(Preference).where(Preference.key == pref_key)
        )
        pref = result.scalar_one_or_none()
        encrypted = encrypt_value(pref_value)
        if pref:
            pref.value = encrypted
        else:
            session.add(Preference(key=pref_key, value=encrypted, category="oauth"))

    await session.commit()


# =============================================================================
# Google Sheets Sync
# =============================================================================


async def sync_from_sheets(
    session: AsyncSession,
    spreadsheet_id: str,
    sheets_service: "GoogleSheetsService",
) -> dict:
    """
    Lance la synchronisation CRM depuis Google Sheets.

    Synchronise : Clients -> Contacts, Projects, Deliverables.

    Returns:
        stats dict avec les compteurs de sync.
    """

    stats = new_sync_stats()

    # Sync Clients
    try:
        clients_data = await sheets_service.get_all_data_as_dicts(spreadsheet_id, "Clients")
        logger.info("Found %d clients in Google Sheets", len(clients_data))

        for raw_row in clients_data:
            try:
                row = _sanitize_row(raw_row)
                _, created = await upsert_contact(session, row, safe_get=True)
                if created:
                    stats["contacts_created"] += 1
                else:
                    stats["contacts_updated"] += 1
            except ValueError:
                continue  # ID manquant, on saute
            except (OSError, RuntimeError) as e:
                logger.error("Error syncing contact %s: %s", row.get('ID', 'unknown'), e)
                stats["errors"].append(f"Contact {row.get('ID', 'unknown')}: {e!s}")

    except (ValueError, OSError, RuntimeError) as e:
        logger.error("Error syncing clients: %s", e)
        stats["errors"].append(f"Clients: {e!s}")

    # Sync Projects
    try:
        projects_data = await sheets_service.get_all_data_as_dicts(spreadsheet_id, "Projects")
        logger.info("Found %d projects in Google Sheets", len(projects_data))

        for raw_row in projects_data:
            try:
                row = _sanitize_row(raw_row)
                _, created = await upsert_project(session, row, safe_get=True)
                if created:
                    stats["projects_created"] += 1
                else:
                    stats["projects_updated"] += 1
            except ValueError:
                continue
            except (OSError, RuntimeError) as e:
                logger.error("Error syncing project %s: %s", row.get('ID', 'unknown'), e)
                stats["errors"].append(f"Project {row.get('ID', 'unknown')}: {e!s}")

    except (ValueError, OSError, RuntimeError) as e:
        logger.error("Error syncing projects: %s", e)
        stats["errors"].append(f"Projects: {e!s}")

    # Sync Tasks
    try:
        tasks_data = await sheets_service.get_all_data_as_dicts(spreadsheet_id, "Tasks")
        logger.info("Found %d tasks in Google Sheets", len(tasks_data))

        for raw_row in tasks_data:
            try:
                row = _sanitize_row(raw_row)
                _, created = await upsert_task(session, row, safe_get=True)
                if created:
                    stats["tasks_created"] += 1
                else:
                    stats["tasks_updated"] += 1
            except ValueError:
                continue
            except (OSError, RuntimeError) as e:
                logger.error("Error syncing task %s: %s", row.get('ID', 'unknown'), e)
                stats["errors"].append(f"Task {row.get('ID', 'unknown')}: {e!s}")

    except (ValueError, OSError, RuntimeError) as e:
        logger.error("Error syncing tasks: %s", e)
        stats["errors"].append(f"Tasks: {e!s}")

    await session.commit()

    return stats


async def import_crm_data_direct(
    session: AsyncSession,
    clients: list[dict] | None = None,
    projects: list[dict] | None = None,
    deliverables: list[dict] | None = None,
    tasks: list[dict] | None = None,
    user_id: str | None = None,
) -> dict:
    """
    Importe les donnees CRM directement (sans passer par Google Sheets API).

    Utilise quand l'acces OAuth/API n'est pas disponible mais qu'on a les donnees
    via d'autres moyens (ex: MCP Claude Code).

    Returns:
        stats dict avec les compteurs d'import.
    """
    stats = new_sync_stats()

    # Import Clients
    if clients:
        logger.info("Importing %d clients (user=%s)", len(clients), user_id)
        for raw_row in clients:
            try:
                row = _sanitize_row(raw_row)
                _, created = await upsert_contact(session, row, safe_get=True)
                if created:
                    stats["contacts_created"] += 1
                else:
                    stats["contacts_updated"] += 1
            except ValueError:
                continue
            except (OSError, RuntimeError) as e:
                logger.error("Error importing contact %s: %s", raw_row.get('ID', 'unknown'), e)
                stats["errors"].append(f"Contact {raw_row.get('ID', 'unknown')}: {e!s}")

    # Import Projects
    if projects:
        logger.info("Importing %d projects (user=%s)", len(projects), user_id)
        for raw_row in projects:
            try:
                row = _sanitize_row(raw_row)
                _, created = await upsert_project(session, row, safe_get=True)
                if created:
                    stats["projects_created"] += 1
                else:
                    stats["projects_updated"] += 1
            except ValueError:
                continue
            except (OSError, RuntimeError) as e:
                logger.error("Error importing project %s: %s", raw_row.get('ID', 'unknown'), e)
                stats["errors"].append(f"Project {raw_row.get('ID', 'unknown')}: {e!s}")

    # Import Deliverables
    if deliverables:
        logger.info("Importing %d deliverables (user=%s)", len(deliverables), user_id)
        for raw_row in deliverables:
            try:
                row = _sanitize_row(raw_row)
                _, created = await upsert_deliverable_from_import(session, row, safe_get=True)
                if created:
                    stats["deliverables_created"] += 1
                else:
                    stats["deliverables_updated"] += 1
            except ValueError:
                continue
            except (OSError, RuntimeError) as e:
                logger.error("Error importing deliverable %s: %s", raw_row.get('ID', 'unknown'), e)
                stats["errors"].append(f"Deliverable {raw_row.get('ID', 'unknown')}: {e!s}")

    # Import Tasks
    if tasks:
        logger.info("Importing %d tasks (user=%s)", len(tasks), user_id)
        for raw_row in tasks:
            try:
                row = _sanitize_row(raw_row)
                _, created = await upsert_task(session, row, safe_get=True)
                if created:
                    stats["tasks_created"] += 1
                else:
                    stats["tasks_updated"] += 1
            except ValueError:
                continue
            except (OSError, RuntimeError) as e:
                logger.error("Error importing task %s: %s", raw_row.get('ID', 'unknown'), e)
                stats["errors"].append(f"Task {raw_row.get('ID', 'unknown')}: {e!s}")

    await session.commit()

    return stats
