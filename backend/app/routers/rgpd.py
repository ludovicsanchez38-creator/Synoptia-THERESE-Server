"""
THÉRÈSE v2 - RGPD Router

Endpoints pour la conformité RGPD :
- Export des données (droit de portabilité)
- Anonymisation (droit à l'oubli)
- Renouvellement du consentement
- Statistiques RGPD
"""

import json
import logging
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.auth.backend import log_audit
from app.auth.rbac import CurrentUser
from app.models.database import get_session
from app.models.entities import (
    Activity,
    BoardDecisionDB,
    Contact,
    Conversation,
    Deliverable,
    FileMetadata,
    Invoice,
    InvoiceLine,
    Message,
    Preference,
    Project,
    PromptTemplate,
    Task,
)
from app.models.schemas import (
    RGPDAnonymizeRequest,
    RGPDAnonymizeResponse,
    RGPDExportResponse,
    RGPDRenewConsentResponse,
    RGPDStatsResponse,
    RGPDUpdateRequest,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["rgpd"])


# ============================================================
# RGPD Export (Droit de portabilité - Art. 20)
# ============================================================


@router.get("/export/{contact_id}", response_model=RGPDExportResponse)
async def export_contact_data(
    contact_id: str,
    current_user: CurrentUser,
    session: AsyncSession = Depends(get_session),
):
    """
    Exporte toutes les données d'un contact (droit de portabilité RGPD).

    Retourne un JSON avec :
    - Données du contact
    - Historique des activités
    - Projets associés
    - Tâches associées
    """
    # Get contact (scope par user)
    result = await session.execute(
        select(Contact).where(Contact.id == contact_id, Contact.user_id == current_user.id)
    )
    contact = result.scalar_one_or_none()

    if not contact:
        raise HTTPException(status_code=404, detail="Contact non trouvé")

    # Get activities
    result = await session.execute(
        select(Activity).where(Activity.contact_id == contact_id)
    )
    activities = result.scalars().all()

    # Get projects
    result = await session.execute(
        select(Project).where(Project.contact_id == contact_id)
    )
    projects = result.scalars().all()

    # Get tasks (via projects)
    project_ids = [p.id for p in projects]
    tasks = []
    if project_ids:
        result = await session.execute(
            select(Task).where(Task.project_id.in_(project_ids))
        )
        tasks = result.scalars().all()

    # Build export
    contact_data = {
        "id": contact.id,
        "first_name": contact.first_name,
        "last_name": contact.last_name,
        "company": contact.company,
        "email": contact.email,
        "phone": contact.phone,
        "notes": contact.notes,
        "tags": contact.tags,
        "stage": contact.stage,
        "score": contact.score,
        "source": contact.source,
        "created_at": contact.created_at.isoformat() if contact.created_at else None,
        "last_interaction": contact.last_interaction.isoformat() if contact.last_interaction else None,
        "rgpd_base_legale": contact.rgpd_base_legale,
        "rgpd_date_collecte": contact.rgpd_date_collecte.isoformat() if contact.rgpd_date_collecte else None,
        "rgpd_date_expiration": contact.rgpd_date_expiration.isoformat() if contact.rgpd_date_expiration else None,
        "rgpd_consentement": contact.rgpd_consentement,
    }

    activities_data = [
        {
            "id": a.id,
            "type": a.type,
            "title": a.title,
            "description": a.description,
            "created_at": a.created_at.isoformat() if a.created_at else None,
        }
        for a in activities
    ]

    projects_data = [
        {
            "id": p.id,
            "name": p.name,
            "description": p.description,
            "status": p.status,
            "budget": p.budget,
            "created_at": p.created_at.isoformat() if p.created_at else None,
        }
        for p in projects
    ]

    tasks_data = [
        {
            "id": t.id,
            "title": t.title,
            "description": t.description,
            "status": t.status,
            "priority": t.priority,
            "due_date": t.due_date.isoformat() if t.due_date else None,
            "created_at": t.created_at.isoformat() if t.created_at else None,
        }
        for t in tasks
    ]

    logger.info(f"RGPD export for contact {contact_id}")

    return RGPDExportResponse(
        contact=contact_data,
        activities=activities_data,
        projects=projects_data,
        tasks=tasks_data,
        exported_at=datetime.utcnow(),
    )


# ============================================================
# RGPD Anonymisation (Droit à l'oubli - Art. 17)
# ============================================================


@router.post("/anonymize/{contact_id}", response_model=RGPDAnonymizeResponse)
async def anonymize_contact(
    contact_id: str,
    request: RGPDAnonymizeRequest,
    current_user: CurrentUser,
    session: AsyncSession = Depends(get_session),
):
    """
    Anonymise un contact (droit à l'oubli RGPD).

    - Remplace les données personnelles par [ANONYMISÉ]
    - Supprime email, téléphone
    - Passe le stage en "archive"
    - Supprime les activités et tâches liées
    - Log l'action avec la raison
    """
    result = await session.execute(
        select(Contact).where(Contact.id == contact_id, Contact.user_id == current_user.id)
    )
    contact = result.scalar_one_or_none()

    if not contact:
        raise HTTPException(status_code=404, detail="Contact non trouvé")

    # Anonymize contact data
    contact.first_name = "[ANONYMISÉ]"
    contact.last_name = None
    contact.email = None
    contact.phone = None
    contact.notes = None
    contact.tags = None
    contact.company = "[ANONYMISÉ]"
    contact.stage = "archive"
    contact.extra_data = None
    contact.updated_at = datetime.utcnow()

    # Delete activities
    result = await session.execute(
        select(Activity).where(Activity.contact_id == contact_id)
    )
    activities = result.scalars().all()
    for activity in activities:
        await session.delete(activity)

    # Delete tasks and projects linked to contact
    result = await session.execute(
        select(Project).where(Project.contact_id == contact_id)
    )
    projects = result.scalars().all()
    for project in projects:
        # Delete tasks of this project
        result = await session.execute(
            select(Task).where(Task.project_id == project.id)
        )
        tasks = result.scalars().all()
        for task in tasks:
            await session.delete(task)
        # Delete deliverables of this project
        result = await session.execute(
            select(Deliverable).where(Deliverable.project_id == project.id)
        )
        deliverables = result.scalars().all()
        for deliv in deliverables:
            await session.delete(deliv)
        # Delete project
        await session.delete(project)

    # Log anonymization activity
    anonymization_log = Activity(
        contact_id=contact_id,
        type="rgpd_anonymization",
        title="Contact anonymisé",
        description=f"Raison: {request.reason}. Contact ID: {contact_id} anonymisé",
    )
    session.add(anonymization_log)

    await session.commit()

    logger.info(f"RGPD anonymization for contact {contact_id}: {request.reason}")

    return RGPDAnonymizeResponse(
        success=True,
        message=f"Contact anonymisé avec succès. Raison: {request.reason}",
        contact_id=contact_id,
    )


# ============================================================
# RGPD Renouvellement Consentement
# ============================================================


@router.post("/renew-consent/{contact_id}", response_model=RGPDRenewConsentResponse)
async def renew_consent(
    contact_id: str,
    current_user: CurrentUser,
    session: AsyncSession = Depends(get_session),
):
    """
    Renouvelle le consentement RGPD d'un contact.

    - Met à jour la date de collecte à aujourd'hui
    - Calcule nouvelle date d'expiration (+3 ans)
    - Passe rgpd_consentement à True
    - Définit la base légale comme "consentement"
    """
    result = await session.execute(
        select(Contact).where(Contact.id == contact_id, Contact.user_id == current_user.id)
    )
    contact = result.scalar_one_or_none()

    if not contact:
        raise HTTPException(status_code=404, detail="Contact non trouvé")

    now = datetime.utcnow()
    new_expiration = now + timedelta(days=3 * 365)  # 3 ans

    contact.rgpd_base_legale = "consentement"
    contact.rgpd_date_collecte = now
    contact.rgpd_date_expiration = new_expiration
    contact.rgpd_consentement = True
    contact.updated_at = now

    # Log activity
    activity = Activity(
        contact_id=contact_id,
        type="rgpd_consent_renewal",
        title="Consentement RGPD renouvelé",
        description=f"Nouvelle expiration: {new_expiration.strftime('%d/%m/%Y')}",
    )
    session.add(activity)

    await session.commit()

    logger.info(f"RGPD consent renewed for contact {contact_id}")

    return RGPDRenewConsentResponse(
        success=True,
        message="Consentement renouvelé avec succès",
        new_expiration=new_expiration,
    )


# ============================================================
# RGPD Update (mise à jour manuelle)
# ============================================================


@router.patch("/{contact_id}", response_model=dict)
async def update_rgpd_fields(
    contact_id: str,
    request: RGPDUpdateRequest,
    current_user: CurrentUser,
    session: AsyncSession = Depends(get_session),
):
    """
    Met à jour les champs RGPD d'un contact.

    Permet de modifier :
    - La base légale
    - Le statut de consentement
    """
    result = await session.execute(
        select(Contact).where(Contact.id == contact_id, Contact.user_id == current_user.id)
    )
    contact = result.scalar_one_or_none()

    if not contact:
        raise HTTPException(status_code=404, detail="Contact non trouvé")

    if request.rgpd_base_legale is not None:
        valid_bases = ["consentement", "contrat", "interet_legitime", "obligation_legale"]
        if request.rgpd_base_legale not in valid_bases:
            raise HTTPException(
                status_code=400,
                detail=f"Base légale invalide. Valeurs acceptées: {valid_bases}"
            )
        contact.rgpd_base_legale = request.rgpd_base_legale

    if request.rgpd_consentement is not None:
        contact.rgpd_consentement = request.rgpd_consentement

    # Auto-set dates if not set
    if contact.rgpd_date_collecte is None:
        contact.rgpd_date_collecte = contact.created_at or datetime.utcnow()

    if contact.rgpd_date_expiration is None:
        base_date = contact.rgpd_date_collecte or datetime.utcnow()
        contact.rgpd_date_expiration = base_date + timedelta(days=3 * 365)

    contact.updated_at = datetime.utcnow()

    await session.commit()

    logger.info(f"RGPD fields updated for contact {contact_id}")

    return {"success": True, "message": "Champs RGPD mis à jour"}


# ============================================================
# RGPD Statistiques
# ============================================================


@router.get("/stats", response_model=RGPDStatsResponse)
async def get_rgpd_stats(
    current_user: CurrentUser,
    session: AsyncSession = Depends(get_session),
):
    """
    Retourne les statistiques RGPD globales.

    - Total contacts
    - Répartition par base légale
    - Contacts sans info RGPD
    - Contacts expirés ou bientôt (30 jours)
    - Contacts avec consentement
    """
    result = await session.execute(
        select(Contact).where(Contact.user_id == current_user.id)
    )
    contacts = result.scalars().all()

    total = len(contacts)
    par_base_legale = {
        "consentement": 0,
        "contrat": 0,
        "interet_legitime": 0,
        "obligation_legale": 0,
        "non_defini": 0,
    }
    sans_info = 0
    expires_ou_bientot = 0
    avec_consentement = 0

    now = datetime.utcnow()
    seuil_30j = now + timedelta(days=30)

    for contact in contacts:
        # Par base légale
        base = contact.rgpd_base_legale
        if base and base in par_base_legale:
            par_base_legale[base] += 1
        else:
            par_base_legale["non_defini"] += 1

        # Sans info RGPD
        if not contact.rgpd_base_legale and not contact.rgpd_date_collecte:
            sans_info += 1

        # Expirés ou bientôt
        if contact.rgpd_date_expiration:
            exp = contact.rgpd_date_expiration
            if exp.tzinfo is None:
                exp = exp.replace(tzinfo=UTC)
            if exp <= seuil_30j:
                expires_ou_bientot += 1

        # Avec consentement
        if contact.rgpd_consentement:
            avec_consentement += 1

    return RGPDStatsResponse(
        total_contacts=total,
        par_base_legale=par_base_legale,
        sans_info_rgpd=sans_info,
        expires_ou_bientot=expires_ou_bientot,
        avec_consentement=avec_consentement,
    )


# ============================================================
# RGPD Auto-inférence base légale
# ============================================================


@router.post("/infer/{contact_id}", response_model=dict)
async def infer_rgpd_base_legale(
    contact_id: str,
    current_user: CurrentUser,
    session: AsyncSession = Depends(get_session),
):
    """
    Infère automatiquement la base légale RGPD d'un contact.

    Logique :
    - Clients actifs/signature/delivery → contrat
    - Prospects (contact/discovery/proposition) → intérêt légitime
    - Si consentement explicite → consentement
    """
    result = await session.execute(
        select(Contact).where(Contact.id == contact_id, Contact.user_id == current_user.id)
    )
    contact = result.scalar_one_or_none()

    if not contact:
        raise HTTPException(status_code=404, detail="Contact non trouvé")

    # Infer base légale
    if contact.rgpd_consentement:
        base_legale = "consentement"
    elif contact.stage in ["active", "signature", "delivery"]:
        base_legale = "contrat"
    else:
        base_legale = "interet_legitime"

    # Set dates if not set
    now = datetime.utcnow()
    if not contact.rgpd_date_collecte:
        contact.rgpd_date_collecte = contact.created_at or now

    # Expiration based on base légale
    if base_legale == "contrat":
        # Durée contrat + 5 ans (obligation comptable)
        expiration = contact.rgpd_date_collecte + timedelta(days=5 * 365)
    else:
        # Prospects: 3 ans après dernier contact
        expiration = contact.rgpd_date_collecte + timedelta(days=3 * 365)

    contact.rgpd_base_legale = base_legale
    contact.rgpd_date_expiration = expiration
    contact.updated_at = now

    await session.commit()

    logger.info(f"RGPD base légale inferred for contact {contact_id}: {base_legale}")

    return {
        "success": True,
        "base_legale": base_legale,
        "date_expiration": expiration.isoformat(),
    }


# ============================================================
# RGPD Utilisateur - Droit de portabilite et droit a l effacement
# Endpoints proteges par authentification JWT
# ============================================================





class UserDataExport(BaseModel):
    """Schema pour l export des donnees utilisateur."""
    user: dict
    conversations: list[dict]
    messages_count: int
    contacts: list[dict]
    projects: list[dict]
    tasks: list[dict]
    files: list[dict]
    preferences: list[dict]
    exported_at: datetime


@router.get("/user/export", response_model=UserDataExport)
async def export_user_data(
    current_user: CurrentUser,
    session: AsyncSession = Depends(get_session),
):
    """
    Exporte toutes les donnees de l utilisateur connecte (Art. 20 RGPD).

    Retourne un JSON contenant conversations, contacts, projets,
    taches, fichiers et preferences.
    """
    user_id = current_user.id

    # Donnees utilisateur
    user_data = {
        "id": current_user.id,
        "email": current_user.email,
        "name": current_user.name,
        "role": current_user.role,
        "created_at": current_user.created_at.isoformat() if current_user.created_at else None,
    }

    # Conversations
    result = await session.execute(
        select(Conversation).where(Conversation.user_id == user_id)
    )
    conversations = result.scalars().all()
    conversations_data = []
    total_messages = 0
    for conv in conversations:
        result = await session.execute(
            select(Message).where(Message.conversation_id == conv.id)
        )
        msgs = result.scalars().all()
        total_messages += len(msgs)
        conversations_data.append({
            "id": conv.id,
            "title": conv.title,
            "created_at": conv.created_at.isoformat() if conv.created_at else None,
            "messages": [
                {
                    "role": m.role,
                    "content": m.content,
                    "model": m.model,
                    "created_at": m.created_at.isoformat() if m.created_at else None,
                }
                for m in msgs
            ],
        })

    # Contacts
    result = await session.execute(
        select(Contact).where(Contact.user_id == user_id)
    )
    contacts = result.scalars().all()
    contacts_data = [
        {
            "id": c.id,
            "first_name": c.first_name,
            "last_name": c.last_name,
            "company": c.company,
            "email": c.email,
            "phone": c.phone,
            "stage": c.stage,
            "created_at": c.created_at.isoformat() if c.created_at else None,
        }
        for c in contacts
    ]

    # Projets
    result = await session.execute(
        select(Project).where(Project.user_id == user_id)
    )
    projects = result.scalars().all()
    projects_data = [
        {
            "id": p.id,
            "name": p.name,
            "description": p.description,
            "status": p.status,
            "created_at": p.created_at.isoformat() if p.created_at else None,
        }
        for p in projects
    ]

    # Taches
    result = await session.execute(
        select(Task).where(Task.user_id == user_id)
    )
    tasks = result.scalars().all()
    tasks_data = [
        {
            "id": t.id,
            "title": t.title,
            "status": t.status,
            "priority": t.priority,
            "due_date": t.due_date.isoformat() if t.due_date else None,
        }
        for t in tasks
    ]

    # Fichiers
    result = await session.execute(
        select(FileMetadata).where(FileMetadata.user_id == user_id)
    )
    files = result.scalars().all()
    files_data = [
        {
            "id": f.id,
            "name": f.name,
            "path": f.path,
            "size": f.size,
            "created_at": f.created_at.isoformat() if f.created_at else None,
        }
        for f in files
    ]

    # Preferences
    result = await session.execute(
        select(Preference).where(Preference.user_id == user_id)
    )
    prefs = result.scalars().all()
    prefs_data = [
        {"key": p.key, "value": p.value, "category": p.category}
        for p in prefs
    ]

    logger.info("RGPD user export for user %s", current_user.email)

    return UserDataExport(
        user=user_data,
        conversations=conversations_data,
        messages_count=total_messages,
        contacts=contacts_data,
        projects=projects_data,
        tasks=tasks_data,
        files=files_data,
        preferences=prefs_data,
        exported_at=datetime.utcnow(),
    )


@router.delete("/user/data")
async def delete_user_data(
    current_user: CurrentUser,
    request_obj: Request = None,
    session: AsyncSession = Depends(get_session),
):
    """
    Supprime toutes les donnees de l utilisateur connecte (Art. 17 RGPD).

    Efface : conversations, messages, contacts, projets, taches,
    fichiers, preferences, decisions, templates, factures.
    Ne supprime PAS le compte utilisateur lui-meme.
    """
    user_id = current_user.id
    deleted = {}

    # Messages (via conversations)
    result = await session.execute(
        select(Conversation).where(Conversation.user_id == user_id)
    )
    conversations = result.scalars().all()
    msg_count = 0
    for conv in conversations:
        result = await session.execute(
            select(Message).where(Message.conversation_id == conv.id)
        )
        msgs = result.scalars().all()
        msg_count += len(msgs)
        for m in msgs:
            await session.delete(m)
    deleted["messages"] = msg_count

    # Conversations
    for conv in conversations:
        await session.delete(conv)
    deleted["conversations"] = len(conversations)

    # Activites (via contacts)
    result = await session.execute(
        select(Contact).where(Contact.user_id == user_id)
    )
    contacts = result.scalars().all()
    for contact in contacts:
        result = await session.execute(
            select(Activity).where(Activity.contact_id == contact.id)
        )
        activities = result.scalars().all()
        for a in activities:
            await session.delete(a)

    # Factures et lignes (via contacts)
    for contact in contacts:
        result = await session.execute(
            select(Invoice).where(Invoice.contact_id == contact.id)
        )
        invoices = result.scalars().all()
        for inv in invoices:
            result = await session.execute(
                select(InvoiceLine).where(InvoiceLine.invoice_id == inv.id)
            )
            lines = result.scalars().all()
            for line in lines:
                await session.delete(line)
            await session.delete(inv)

    # Contacts
    for c in contacts:
        await session.delete(c)
    deleted["contacts"] = len(contacts)

    # Projets, taches, livrables
    result = await session.execute(
        select(Project).where(Project.user_id == user_id)
    )
    projects = result.scalars().all()
    for p in projects:
        result = await session.execute(
            select(Task).where(Task.project_id == p.id)
        )
        for t in result.scalars().all():
            await session.delete(t)
        result = await session.execute(
            select(Deliverable).where(Deliverable.project_id == p.id)
        )
        for d in result.scalars().all():
            await session.delete(d)
        await session.delete(p)
    deleted["projects"] = len(projects)

    # Taches orphelines
    result = await session.execute(
        select(Task).where(Task.user_id == user_id)
    )
    tasks = result.scalars().all()
    for t in tasks:
        await session.delete(t)
    deleted["tasks"] = len(tasks)

    # Fichiers
    result = await session.execute(
        select(FileMetadata).where(FileMetadata.user_id == user_id)
    )
    files = result.scalars().all()
    for f in files:
        await session.delete(f)
    deleted["files"] = len(files)

    # Preferences
    result = await session.execute(
        select(Preference).where(Preference.user_id == user_id)
    )
    prefs = result.scalars().all()
    for p in prefs:
        await session.delete(p)
    deleted["preferences"] = len(prefs)

    # Decisions Board
    result = await session.execute(
        select(BoardDecisionDB).where(BoardDecisionDB.user_id == user_id)
    )
    decisions = result.scalars().all()
    for d in decisions:
        await session.delete(d)
    deleted["board_decisions"] = len(decisions)

    # Templates
    result = await session.execute(
        select(PromptTemplate).where(PromptTemplate.user_id == user_id)
    )
    templates = result.scalars().all()
    for t in templates:
        await session.delete(t)
    deleted["prompt_templates"] = len(templates)

    await session.commit()

    # Audit (dans une nouvelle transaction, car les donnees sont deja supprimees)
    await log_audit(
        session=session,
        user_id=current_user.id,
        org_id=current_user.org_id,
        action="rgpd_delete_all_data",
        resource="user_data",
        details_json=json.dumps(deleted),
        user_email=current_user.email,
    )

    logger.info("RGPD data deletion for user %s: %s", current_user.email, deleted)

    return {
        "success": True,
        "message": "Toutes vos donnees ont ete supprimees",
        "deleted": deleted,
    }
