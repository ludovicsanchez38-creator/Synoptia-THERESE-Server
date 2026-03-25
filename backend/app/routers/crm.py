"""
THERESE v2 - CRM Router

REST API pour les features CRM (pipeline, scoring, activites, livrables, sync Google Sheets).
Phase 5 - CRM Features + Local First Export/Import

Logique metier extraite vers services/crm_service.py.
"""

import logging
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.auth.rbac import CurrentUser
from app.auth.tenant import get_owned, set_owner
from app.models.database import get_session
from app.models.entities import Activity, Contact, Deliverable, Preference, Project
from app.models.schemas import (
    ActivityResponse,
    ContactResponse,
    ContactScoreUpdate,
    CreateActivityRequest,
    CreateCRMContactRequest,
    CreateDeliverableRequest,
    CRMImportErrorSchema,
    CRMImportPreviewSchema,
    CRMImportResultSchema,
    CRMSyncConfigRequest,
    CRMSyncConfigResponse,
    CRMSyncResponse,
    CRMSyncStatsResponse,
    DeliverableResponse,
    UpdateContactStageRequest,
    UpdateDeliverableRequest,
)
from app.services.crm_export import CRMExportService, ExportFormat
from app.services.crm_import import CRMImportService
from app.services.crm_service import (
    change_contact_stage,
    discover_google_credentials,
    import_crm_data_direct,
    push_contact_to_sheets,
    sync_from_sheets,
    upsert_sync_spreadsheet_id,
)
from app.services.crm_service import (
    get_pipeline_stats as _get_pipeline_stats,
)
from app.services.crm_service import (
    get_sync_config as _get_sync_config,
)
from app.services.crm_service import (
    save_google_credentials as _save_google_credentials,
)
from app.services.crm_utils import (
    compute_total_synced,
    update_last_sync_time,
)
from app.services.oauth import (
    GOOGLE_AUTH_URL,
    GOOGLE_TOKEN_URL,
    GSHEETS_SCOPES,
    RUNTIME_PORT,
    OAuthConfig,
    get_oauth_service,
)
from app.services.scoring import update_contact_score

logger = logging.getLogger(__name__)

router = APIRouter(tags=["crm"])


# =============================================================================
# ACTIVITIES (Timeline)
# =============================================================================


def _activity_to_response(activity: Activity) -> ActivityResponse:
    """Convertit Activity entity en ActivityResponse schema."""
    return ActivityResponse(
        id=activity.id,
        contact_id=activity.contact_id,
        type=activity.type,
        title=activity.title,
        description=activity.description,
        extra_data=activity.extra_data,
        created_at=activity.created_at.isoformat(),
    )


@router.get("/activities", response_model=list[ActivityResponse])
async def list_activities(
    current_user: CurrentUser,
    contact_id: str | None = Query(None, description="Filtrer par contact"),
    type: str | None = Query(None, description="Filtrer par type"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    session: AsyncSession = Depends(get_session),
):
    """Liste les activites avec pagination et filtres."""
    statement = (
        select(Activity)
        .join(Contact, Activity.contact_id == Contact.id)
        .where(Contact.user_id == current_user.id)
    )
    if contact_id:
        statement = statement.where(Activity.contact_id == contact_id)
    if type:
        statement = statement.where(Activity.type == type)

    statement = statement.order_by(Activity.created_at.desc()).offset(skip).limit(limit)
    result = await session.execute(statement)
    activities = result.scalars().all()
    return [_activity_to_response(activity) for activity in activities]


@router.post("/activities", response_model=ActivityResponse)
async def create_activity(
    request: CreateActivityRequest,
    current_user: CurrentUser,
    session: AsyncSession = Depends(get_session),
):
    """Cree une nouvelle activite dans la timeline."""
    contact = await get_owned(session, Contact, request.contact_id, current_user)
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")

    activity = Activity(
        contact_id=request.contact_id,
        type=request.type,
        title=request.title,
        description=request.description,
        extra_data=request.extra_data,
    )
    session.add(activity)

    contact.last_interaction = datetime.now(UTC)
    contact.updated_at = datetime.now(UTC)
    session.add(contact)

    if request.type in ["email", "call", "meeting"]:
        await update_contact_score(session, contact, reason=f"interaction_{request.type}")

    await session.commit()
    await session.refresh(activity)
    logger.info("Activity created: %s for contact %s (user=%s)", activity.id, contact.id, current_user.id)
    return _activity_to_response(activity)


@router.delete("/activities/{activity_id}")
async def delete_activity(
    activity_id: str,
    current_user: CurrentUser,
    session: AsyncSession = Depends(get_session),
):
    """Supprime une activite."""
    stmt = (
        select(Activity)
        .join(Contact, Activity.contact_id == Contact.id)
        .where(Activity.id == activity_id, Contact.user_id == current_user.id)
    )
    result = await session.execute(stmt)
    activity = result.scalar_one_or_none()
    if not activity:
        raise HTTPException(status_code=404, detail="Activity not found")

    await session.delete(activity)
    await session.commit()
    logger.info("Activity deleted: %s (user=%s)", activity_id, current_user.id)
    return {"message": "Activity deleted successfully"}


# =============================================================================
# DELIVERABLES (Livrables)
# =============================================================================


def _deliverable_to_response(deliverable: Deliverable) -> DeliverableResponse:
    """Convertit Deliverable entity en DeliverableResponse schema."""
    return DeliverableResponse(
        id=deliverable.id,
        project_id=deliverable.project_id,
        title=deliverable.title,
        description=deliverable.description,
        status=deliverable.status,
        due_date=deliverable.due_date.isoformat() if deliverable.due_date else None,
        completed_at=deliverable.completed_at.isoformat() if deliverable.completed_at else None,
        created_at=deliverable.created_at.isoformat(),
        updated_at=deliverable.updated_at.isoformat(),
    )


@router.get("/deliverables", response_model=list[DeliverableResponse])
async def list_deliverables(
    current_user: CurrentUser,
    project_id: str | None = Query(None, description="Filtrer par projet"),
    status: str | None = Query(None, description="Filtrer par status"),
    session: AsyncSession = Depends(get_session),
):
    """Liste les livrables avec filtres."""
    statement = (
        select(Deliverable)
        .join(Project, Deliverable.project_id == Project.id)
        .where(Project.user_id == current_user.id)
    )
    if project_id:
        statement = statement.where(Deliverable.project_id == project_id)
    if status:
        statement = statement.where(Deliverable.status == status)

    statement = statement.order_by(Deliverable.created_at.desc())
    result = await session.execute(statement)
    deliverables = result.scalars().all()
    return [_deliverable_to_response(d) for d in deliverables]


@router.post("/deliverables", response_model=DeliverableResponse)
async def create_deliverable(
    request: CreateDeliverableRequest,
    current_user: CurrentUser,
    session: AsyncSession = Depends(get_session),
):
    """Cree un nouveau livrable."""
    project = await get_owned(session, Project, request.project_id, current_user)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    due_date = None
    if request.due_date:
        due_date = datetime.fromisoformat(request.due_date.replace("Z", ""))

    deliverable = Deliverable(
        project_id=request.project_id,
        title=request.title,
        description=request.description,
        status=request.status,
        due_date=due_date,
    )
    session.add(deliverable)
    await session.commit()
    await session.refresh(deliverable)
    logger.info("Deliverable created: %s for project %s (user=%s)", deliverable.id, project.id, current_user.id)
    return _deliverable_to_response(deliverable)


@router.put("/deliverables/{deliverable_id}", response_model=DeliverableResponse)
async def update_deliverable(
    deliverable_id: str,
    request: UpdateDeliverableRequest,
    current_user: CurrentUser,
    session: AsyncSession = Depends(get_session),
):
    """Met a jour un livrable."""
    stmt = (
        select(Deliverable)
        .join(Project, Deliverable.project_id == Project.id)
        .where(Deliverable.id == deliverable_id, Project.user_id == current_user.id)
    )
    result = await session.execute(stmt)
    deliverable = result.scalar_one_or_none()
    if not deliverable:
        raise HTTPException(status_code=404, detail="Deliverable not found")

    if request.title is not None:
        deliverable.title = request.title
    if request.description is not None:
        deliverable.description = request.description
    if request.status is not None:
        deliverable.status = request.status
        if request.status == "valide" and deliverable.completed_at is None:
            deliverable.completed_at = datetime.now(UTC)
    if request.due_date is not None:
        deliverable.due_date = datetime.fromisoformat(request.due_date.replace("Z", ""))

    deliverable.updated_at = datetime.now(UTC)
    session.add(deliverable)
    await session.commit()
    await session.refresh(deliverable)
    logger.info("Deliverable updated: %s (user=%s)", deliverable_id, current_user.id)
    return _deliverable_to_response(deliverable)


@router.delete("/deliverables/{deliverable_id}")
async def delete_deliverable(
    deliverable_id: str,
    current_user: CurrentUser,
    session: AsyncSession = Depends(get_session),
):
    """Supprime un livrable."""
    stmt = (
        select(Deliverable)
        .join(Project, Deliverable.project_id == Project.id)
        .where(Deliverable.id == deliverable_id, Project.user_id == current_user.id)
    )
    result = await session.execute(stmt)
    deliverable = result.scalar_one_or_none()
    if not deliverable:
        raise HTTPException(status_code=404, detail="Deliverable not found")

    await session.delete(deliverable)
    await session.commit()
    logger.info("Deliverable deleted: %s (user=%s)", deliverable_id, current_user.id)
    return {"message": "Deliverable deleted successfully"}


# =============================================================================
# CRM CONTACTS
# =============================================================================


@router.post("/contacts", response_model=ContactResponse)
async def create_crm_contact(
    request: CreateCRMContactRequest,
    current_user: CurrentUser,
    session: AsyncSession = Depends(get_session),
):
    """Cree un contact CRM et tente de l'ajouter au Google Sheets."""
    import uuid

    source = request.source.strip() if request.source else "THERESE"

    contact = Contact(
        id=str(uuid.uuid4()),
        first_name=request.first_name.strip(),
        last_name=request.last_name.strip() if request.last_name else None,
        company=request.company.strip() if request.company else None,
        email=request.email.strip() if request.email else None,
        phone=request.phone.strip() if request.phone else None,
        source=source,
        stage=request.stage,
        score=50,
        scope="global",
    )
    set_owner(contact, current_user)
    session.add(contact)
    await session.commit()
    await session.refresh(contact)

    logger.info("CRM contact created: %s (%s %s) (user=%s)", contact.id, contact.first_name, contact.last_name, current_user.id)

    # Push to Google Sheets (best effort)
    await push_contact_to_sheets(session, contact, source)

    from app.routers.memory import _contact_to_response
    return _contact_to_response(contact)


# =============================================================================
# PIPELINE (Stages & Scoring)
# =============================================================================


@router.patch("/contacts/{contact_id}/stage", response_model=ContactResponse)
async def update_contact_stage(
    contact_id: str,
    request: UpdateContactStageRequest,
    current_user: CurrentUser,
    session: AsyncSession = Depends(get_session),
):
    """Change le stage d'un contact dans le pipeline."""
    contact = await get_owned(session, Contact, contact_id, current_user)
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")

    await change_contact_stage(session, contact, request.stage)
    await session.commit()
    await session.refresh(contact)

    logger.info("Contact %s stage updated (user=%s)", contact_id, current_user.id)

    from app.routers.memory import _contact_to_response
    return _contact_to_response(contact)


@router.post("/contacts/{contact_id}/recalculate-score", response_model=ContactScoreUpdate)
async def recalculate_contact_score(
    contact_id: str,
    current_user: CurrentUser,
    session: AsyncSession = Depends(get_session),
):
    """Recalcule manuellement le score d'un contact."""
    contact = await get_owned(session, Contact, contact_id, current_user)
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")

    result = await update_contact_score(session, contact, reason="manual_recalculation")
    await session.commit()
    return ContactScoreUpdate(**result)


@router.get("/pipeline/stats")
async def get_pipeline_stats(
    current_user: CurrentUser,
    session: AsyncSession = Depends(get_session),
):
    """Retourne des statistiques sur le pipeline commercial."""
    return await _get_pipeline_stats(session, current_user.id)


# =============================================================================
# CRM EXPORT (Local First)
# =============================================================================


@router.post("/export/contacts")
async def export_contacts(
    current_user: CurrentUser,
    format: ExportFormat = Query("csv", description="Format d'export (csv, xlsx, json)"),
    stage: str | None = Query(None, description="Filtrer par stage"),
    source: str | None = Query(None, description="Filtrer par source"),
    session: AsyncSession = Depends(get_session),
):
    """Exporte les contacts au format CSV, Excel ou JSON."""
    export_service = CRMExportService(session)
    result = await export_service.export_contacts(format=format, stage=stage, source=source)
    logger.info("Exported %d contacts to %s (user=%s)", result.row_count, format, current_user.id)
    return Response(
        content=result.data,
        media_type=result.content_type,
        headers={
            "Content-Disposition": f'attachment; filename="{result.filename}"',
            "X-Row-Count": str(result.row_count),
        },
    )


@router.post("/export/projects")
async def export_projects(
    current_user: CurrentUser,
    format: ExportFormat = Query("csv", description="Format d'export (csv, xlsx, json)"),
    status: str | None = Query(None, description="Filtrer par statut"),
    contact_id: str | None = Query(None, description="Filtrer par contact"),
    session: AsyncSession = Depends(get_session),
):
    """Exporte les projets au format CSV, Excel ou JSON."""
    export_service = CRMExportService(session)
    result = await export_service.export_projects(format=format, status=status, contact_id=contact_id)
    logger.info("Exported %d projects to %s (user=%s)", result.row_count, format, current_user.id)
    return Response(
        content=result.data,
        media_type=result.content_type,
        headers={
            "Content-Disposition": f'attachment; filename="{result.filename}"',
            "X-Row-Count": str(result.row_count),
        },
    )


@router.post("/export/deliverables")
async def export_deliverables(
    current_user: CurrentUser,
    format: ExportFormat = Query("csv", description="Format d'export (csv, xlsx, json)"),
    status: str | None = Query(None, description="Filtrer par statut"),
    project_id: str | None = Query(None, description="Filtrer par projet"),
    session: AsyncSession = Depends(get_session),
):
    """Exporte les livrables au format CSV, Excel ou JSON."""
    export_service = CRMExportService(session)
    result = await export_service.export_deliverables(format=format, status=status, project_id=project_id)
    logger.info("Exported %d deliverables to %s (user=%s)", result.row_count, format, current_user.id)
    return Response(
        content=result.data,
        media_type=result.content_type,
        headers={
            "Content-Disposition": f'attachment; filename="{result.filename}"',
            "X-Row-Count": str(result.row_count),
        },
    )


@router.post("/export/all")
async def export_all_crm(
    current_user: CurrentUser,
    format: ExportFormat = Query("xlsx", description="Format d'export (csv, xlsx, json)"),
    session: AsyncSession = Depends(get_session),
):
    """Exporte toutes les donnees CRM."""
    export_service = CRMExportService(session)
    result = await export_service.export_all(format=format)
    logger.info("Exported all CRM data (%d total rows) to %s (user=%s)", result.row_count, format, current_user.id)
    return Response(
        content=result.data,
        media_type=result.content_type,
        headers={
            "Content-Disposition": f'attachment; filename="{result.filename}"',
            "X-Row-Count": str(result.row_count),
        },
    )


# =============================================================================
# CRM IMPORT (Local First)
# =============================================================================


@router.post("/import/contacts/preview", response_model=CRMImportPreviewSchema)
async def preview_contacts_import(
    current_user: CurrentUser,
    file: UploadFile = File(..., description="Fichier CSV, Excel ou JSON"),
    session: AsyncSession = Depends(get_session),
):
    """Preview d'import de contacts sans execution."""
    content = await file.read()
    import_service = CRMImportService(session)
    preview = await import_service.preview_contacts(content, filename=file.filename)

    return CRMImportPreviewSchema(
        total_rows=preview.total_rows,
        sample_rows=preview.sample_rows,
        detected_columns=preview.detected_columns,
        column_mapping=preview.column_mapping,
        validation_errors=[
            CRMImportErrorSchema(row=e.row, column=e.column, message=e.message, data=e.data)
            for e in preview.validation_errors
        ],
        can_import=preview.can_import,
    )


@router.post("/import/contacts", response_model=CRMImportResultSchema)
async def import_contacts(
    current_user: CurrentUser,
    file: UploadFile = File(..., description="Fichier CSV, Excel ou JSON"),
    update_existing: bool = Query(True, description="Mettre a jour les contacts existants"),
    session: AsyncSession = Depends(get_session),
):
    """Importe des contacts depuis un fichier CSV, Excel ou JSON."""
    content = await file.read()
    import_service = CRMImportService(session)
    result = await import_service.import_contacts(content, filename=file.filename, update_existing=update_existing)
    logger.info("Contacts import: %s (user=%s)", result.message, current_user.id)

    return CRMImportResultSchema(
        success=result.success, created=result.created, updated=result.updated,
        skipped=result.skipped,
        errors=[CRMImportErrorSchema(row=e.row, column=e.column, message=e.message, data=e.data) for e in result.errors],
        total_rows=result.total_rows, message=result.message,
    )


@router.post("/import/projects", response_model=CRMImportResultSchema)
async def import_projects(
    current_user: CurrentUser,
    file: UploadFile = File(..., description="Fichier CSV, Excel ou JSON"),
    update_existing: bool = Query(True, description="Mettre a jour les projets existants"),
    session: AsyncSession = Depends(get_session),
):
    """Importe des projets depuis un fichier CSV, Excel ou JSON."""
    content = await file.read()
    import_service = CRMImportService(session)
    result = await import_service.import_projects(content, filename=file.filename, update_existing=update_existing)
    logger.info("Projects import: %s (user=%s)", result.message, current_user.id)

    return CRMImportResultSchema(
        success=result.success, created=result.created, updated=result.updated,
        skipped=result.skipped,
        errors=[CRMImportErrorSchema(row=e.row, column=e.column, message=e.message, data=e.data) for e in result.errors],
        total_rows=result.total_rows, message=result.message,
    )


@router.post("/import/deliverables", response_model=CRMImportResultSchema)
async def import_deliverables(
    current_user: CurrentUser,
    file: UploadFile = File(..., description="Fichier CSV, Excel ou JSON"),
    update_existing: bool = Query(True, description="Mettre a jour les livrables existants"),
    session: AsyncSession = Depends(get_session),
):
    """Importe des livrables depuis un fichier CSV, Excel ou JSON."""
    content = await file.read()
    import_service = CRMImportService(session)
    result = await import_service.import_deliverables(content, filename=file.filename, update_existing=update_existing)
    logger.info("Deliverables import: %s (user=%s)", result.message, current_user.id)

    return CRMImportResultSchema(
        success=result.success, created=result.created, updated=result.updated,
        skipped=result.skipped,
        errors=[CRMImportErrorSchema(row=e.row, column=e.column, message=e.message, data=e.data) for e in result.errors],
        total_rows=result.total_rows, message=result.message,
    )


# =============================================================================
# CRM SYNC (Google Sheets)
# =============================================================================


@router.get("/sync/config", response_model=CRMSyncConfigResponse)
async def get_sync_config(
    current_user: CurrentUser,
    session: AsyncSession = Depends(get_session),
):
    """Recupere la configuration de synchronisation CRM."""
    config = await _get_sync_config(session)
    return CRMSyncConfigResponse(**config)


@router.post("/sync/config", response_model=CRMSyncConfigResponse)
async def set_sync_config(
    request: CRMSyncConfigRequest,
    current_user: CurrentUser,
    session: AsyncSession = Depends(get_session),
):
    """Configure le spreadsheet ID pour la synchronisation CRM."""
    spreadsheet_id = request.spreadsheet_id.strip()
    if not spreadsheet_id:
        raise HTTPException(status_code=400, detail="Spreadsheet ID cannot be empty")

    await upsert_sync_spreadsheet_id(session, spreadsheet_id)
    logger.info("CRM sync configured with spreadsheet: %s... (user=%s)", spreadsheet_id[:20], current_user.id)

    config = await _get_sync_config(session)
    return CRMSyncConfigResponse(**config)


@router.post("/sync/credentials")
async def save_google_credentials(
    request: dict,
    current_user: CurrentUser,
    session: AsyncSession = Depends(get_session),
):
    """F-13 : Re-saisie des credentials Google OAuth."""
    client_id = request.get("client_id", "").strip()
    client_secret = request.get("client_secret", "").strip()

    if not client_id or not client_secret:
        raise HTTPException(status_code=400, detail="client_id et client_secret sont requis")

    if not client_id.endswith(".apps.googleusercontent.com"):
        raise HTTPException(status_code=400, detail="Le client_id doit se terminer par .apps.googleusercontent.com")

    if not client_secret.startswith("GOCSPX-"):
        raise HTTPException(status_code=400, detail="Le client_secret doit commencer par GOCSPX-")

    await _save_google_credentials(session, client_id, client_secret)
    logger.info("Google OAuth credentials saved via F-13 re-entry (user=%s)", current_user.id)

    return {"success": True, "message": "Credentials Google OAuth enregistrees"}


@router.post("/sync/connect")
async def initiate_sheets_oauth(
    current_user: CurrentUser,
    session: AsyncSession = Depends(get_session),
):
    """Lance le flux OAuth pour connecter Google Sheets."""
    client_id, client_secret = await discover_google_credentials(session)

    if not client_id or not client_secret:
        raise HTTPException(
            status_code=400,
            detail="Credentials Google OAuth introuvables. Configure d'abord ton email Gmail dans THERESE, ou ajoute un serveur MCP Google Workspace.",
        )

    config = OAuthConfig(
        client_id=client_id,
        client_secret=client_secret,
        auth_url=GOOGLE_AUTH_URL,
        token_url=GOOGLE_TOKEN_URL,
        scopes=GSHEETS_SCOPES,
        redirect_uri=f"http://localhost:{RUNTIME_PORT}/api/crm/sync/callback",
    )

    oauth_service = get_oauth_service()
    result = oauth_service.initiate_flow("gsheets", config)

    return {
        "auth_url": result["auth_url"],
        "state": result["state"],
        "message": "Ouvrez cette URL dans votre navigateur pour autoriser l'acces a Google Sheets",
    }


@router.get("/sync/callback")
async def handle_sheets_oauth_callback(
    state: str,
    code: str | None = None,
    error: str | None = None,
    session: AsyncSession = Depends(get_session),
):
    """Callback OAuth pour Google Sheets."""
    oauth_service = get_oauth_service()
    tokens = await oauth_service.handle_callback(state, code, error)

    from app.services.crm_sync import auto_create_crm_spreadsheet, set_crm_tokens
    await set_crm_tokens(
        session,
        tokens["access_token"],
        tokens.get("refresh_token"),
        client_id=tokens.get("client_id"),
        client_secret=tokens.get("client_secret"),
    )

    spreadsheet_info = await auto_create_crm_spreadsheet(session, tokens["access_token"])

    result = {"success": True, "message": "Google Sheets connecte avec succes"}
    if spreadsheet_info:
        result["spreadsheet_id"] = spreadsheet_info["spreadsheet_id"]
        result["spreadsheet_url"] = spreadsheet_info["spreadsheet_url"]
        result["message"] = "Google Sheets connecte et CRM cree automatiquement"

    return result


@router.post("/sync", response_model=CRMSyncResponse)
async def sync_crm(
    current_user: CurrentUser,
    session: AsyncSession = Depends(get_session),
):
    """Lance la synchronisation CRM depuis Google Sheets."""
    from app.services.crm_sync import ensure_valid_crm_token
    from app.services.encryption import decrypt_value
    from app.services.sheets_service import GoogleSheetsService

    # Get spreadsheet ID
    result = await session.execute(
        select(Preference).where(Preference.key == "crm_spreadsheet_id")
    )
    spreadsheet_pref = result.scalar_one_or_none()
    if not spreadsheet_pref or not spreadsheet_pref.value:
        raise HTTPException(status_code=400, detail="Spreadsheet ID non configure. Utilisez POST /api/crm/sync/config d'abord.")

    spreadsheet_id = spreadsheet_pref.value

    # Resolve authentication
    access_token = await ensure_valid_crm_token(session)
    api_key = None

    if not access_token:
        result = await session.execute(
            select(Preference).where(Preference.key == "gemini_api_key")
        )
        gemini_pref = result.scalar_one_or_none()
        if gemini_pref and gemini_pref.value:
            try:
                api_key = decrypt_value(gemini_pref.value)
            except (ValueError, OSError):
                api_key = None

    if not access_token and not api_key:
        raise HTTPException(status_code=401, detail="Aucune authentification disponible. Connectez Google Sheets (OAuth) ou configurez une cle API Gemini.")

    try:
        sheets_service = GoogleSheetsService(access_token=access_token, api_key=api_key)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    try:
        stats = await sync_from_sheets(session, spreadsheet_id, sheets_service)
        now = await update_last_sync_time(session)
        total_synced = compute_total_synced(stats)

        return CRMSyncResponse(
            success=len(stats["errors"]) == 0,
            message=f"Synchronisation terminee: {total_synced} elements",
            stats=CRMSyncStatsResponse(**stats, total_synced=total_synced),
            sync_time=now,
        )
    except HTTPException:
        raise
    except (ValueError, OSError, RuntimeError) as e:
        logger.error("CRM sync failed: %s", e)
        raise HTTPException(status_code=500, detail=f"Erreur de synchronisation: {e!s}")


@router.post("/sync/import", response_model=CRMSyncResponse)
async def import_crm_data(
    current_user: CurrentUser,
    clients: list[dict] | None = None,
    projects: list[dict] | None = None,
    deliverables: list[dict] | None = None,
    tasks: list[dict] | None = None,
    session: AsyncSession = Depends(get_session),
):
    """Importe les donnees CRM directement (sans Google Sheets API)."""
    stats = await import_crm_data_direct(
        session,
        clients=clients,
        projects=projects,
        deliverables=deliverables,
        tasks=tasks,
        user_id=current_user.id,
    )

    now = await update_last_sync_time(session)
    total_synced = compute_total_synced(stats)

    return CRMSyncResponse(
        success=len(stats["errors"]) == 0,
        message=f"Import termine: {total_synced} elements",
        stats=CRMSyncStatsResponse(**stats, total_synced=total_synced),
        sync_time=now,
    )
