"""
Therese Server - Prompt Templates Router

CRUD + seed de modeles de prompts pour collectivites et PME.
"""

import logging
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import or_, select

from app.auth.models import User
from app.auth.rbac import CurrentUser, RequireAdmin
from app.auth.tenant import get_owned, set_owner
from app.models.database import get_session
from app.models.entities import PromptTemplate

logger = logging.getLogger(__name__)
router = APIRouter()


# --- Schemas ---


class TemplateCreate(BaseModel):
    name: str
    prompt: str
    category: str = "general"
    icon: str | None = None


class TemplateUpdate(BaseModel):
    name: str | None = None
    prompt: str | None = None
    category: str | None = None
    icon: str | None = None


class TemplateResponse(BaseModel):
    id: str
    name: str
    prompt: str
    category: str
    icon: str | None
    user_id: str | None
    org_id: str | None
    created_at: datetime
    updated_at: datetime


VALID_CATEGORIES = {
    "courrier",
    "deliberation",
    "note",
    "synthese",
    "communication",
    "rh",
    "general",
}

# --- Templates par defaut (secteur public + PME) ---

DEFAULT_TEMPLATES: list[dict] = [
    {
        "name": "Courrier administratif",
        "category": "courrier",
        "icon": "Mail",
        "prompt": (
            "R\u00e9dige un courrier administratif formel de la part de [service] "
            "\u00e0 destination de [destinataire] concernant [sujet]. "
            "Ton professionnel, formules de politesse adapt\u00e9es au secteur public."
        ),
    },
    {
        "name": "R\u00e9ponse \u00e0 un administr\u00e9",
        "category": "courrier",
        "icon": "Mail",
        "prompt": (
            "R\u00e9dige une r\u00e9ponse \u00e0 un administr\u00e9 qui a \u00e9crit au sujet de [sujet]. "
            "La r\u00e9ponse doit \u00eatre courtoise, claire et indiquer les prochaines \u00e9tapes."
        ),
    },
    {
        "name": "Note de synth\u00e8se",
        "category": "synthese",
        "icon": "ClipboardList",
        "prompt": (
            "R\u00e9dige une note de synth\u00e8se sur [sujet] \u00e0 destination de [destinataire]. "
            "Structure : contexte, enjeux, analyse, recommandations. Maximum 2 pages."
        ),
    },
    {
        "name": "Compte-rendu de r\u00e9union",
        "category": "note",
        "icon": "FileText",
        "prompt": (
            "R\u00e9dige un compte-rendu structur\u00e9 de la r\u00e9union du [date] portant sur [sujet]. "
            "Participants : [liste]. Inclure : points abord\u00e9s, d\u00e9cisions prises, "
            "actions \u00e0 mener avec responsables et d\u00e9lais."
        ),
    },
    {
        "name": "D\u00e9lib\u00e9ration du conseil",
        "category": "deliberation",
        "icon": "Scale",
        "prompt": (
            "R\u00e9dige un projet de d\u00e9lib\u00e9ration pour le conseil municipal/d'administration "
            "portant sur [sujet]. Structure : visa des textes, expos\u00e9 des motifs, "
            "dispositif (articles)."
        ),
    },
    {
        "name": "Communication interne",
        "category": "communication",
        "icon": "Megaphone",
        "prompt": (
            "R\u00e9dige une note d'information interne \u00e0 destination de "
            "[service/tous les agents] concernant [sujet]. "
            "Ton accessible, informations pratiques, dates cl\u00e9s."
        ),
    },
    {
        "name": "Offre d'emploi",
        "category": "rh",
        "icon": "Users",
        "prompt": (
            "R\u00e9dige une offre d'emploi pour le poste de [intitul\u00e9] au sein de [service]. "
            "Inclure : missions, profil recherch\u00e9, conditions (grade, r\u00e9mun\u00e9ration), "
            "modalit\u00e9s de candidature."
        ),
    },
    {
        "name": "Synth\u00e8se de document",
        "category": "synthese",
        "icon": "ClipboardList",
        "prompt": (
            "R\u00e9sume le document suivant en [nombre] points cl\u00e9s. "
            "Identifie les informations essentielles, les d\u00e9cisions \u00e0 prendre "
            "et les d\u00e9lais importants."
        ),
    },
    {
        "name": "Email professionnel",
        "category": "communication",
        "icon": "Megaphone",
        "prompt": (
            "R\u00e9dige un email professionnel \u00e0 [destinataire] concernant [sujet]. "
            "Ton : [formel/cordial]. Objectif : [informer/demander/confirmer]."
        ),
    },
    {
        "name": "Analyse comparative",
        "category": "general",
        "icon": "Sparkles",
        "prompt": (
            "R\u00e9alise une analyse comparative entre [option A] et [option B] "
            "pour [contexte]. Structure en tableau avec crit\u00e8res : co\u00fbt, d\u00e9lai, "
            "avantages, inconv\u00e9nients, recommandation."
        ),
    },
]


# --- Endpoints ---


@router.get("", response_model=list[TemplateResponse])
async def list_templates(
    current_user: CurrentUser,
    category: str | None = Query(default=None, description="Filtrer par cat\u00e9gorie"),
    session: AsyncSession = Depends(get_session),
):
    """Lister les templates : personnels + partag\u00e9s de l'organisation."""
    stmt = select(PromptTemplate).where(
        or_(
            PromptTemplate.user_id == current_user.id,
            (PromptTemplate.user_id.is_(None)) & (PromptTemplate.org_id == current_user.org_id),
        )
    )
    if category:
        if category not in VALID_CATEGORIES:
            raise HTTPException(
                status_code=400,
                detail=f"Cat\u00e9gorie invalide. Valeurs possibles : {', '.join(sorted(VALID_CATEGORIES))}",
            )
        stmt = stmt.where(PromptTemplate.category == category)

    stmt = stmt.order_by(PromptTemplate.category, PromptTemplate.name)
    result = await session.execute(stmt)
    templates = result.scalars().all()

    return [
        TemplateResponse(
            id=t.id,
            name=t.name,
            prompt=t.prompt,
            category=t.category,
            icon=t.icon,
            user_id=t.user_id,
            org_id=t.org_id,
            created_at=t.created_at,
            updated_at=t.updated_at,
        )
        for t in templates
    ]


@router.post("", response_model=TemplateResponse, status_code=201)
async def create_template(
    current_user: CurrentUser,
    body: TemplateCreate,
    session: AsyncSession = Depends(get_session),
):
    """Cr\u00e9er un template personnel."""
    if body.category not in VALID_CATEGORIES:
        raise HTTPException(
            status_code=400,
            detail=f"Cat\u00e9gorie invalide. Valeurs possibles : {', '.join(sorted(VALID_CATEGORIES))}",
        )

    template = PromptTemplate(
        name=body.name,
        prompt=body.prompt,
        category=body.category,
        icon=body.icon,
    )
    set_owner(template, current_user)

    session.add(template)
    await session.commit()
    await session.refresh(template)

    logger.info("Template cr\u00e9\u00e9 : %s (user=%s)", template.name, current_user.id)

    return TemplateResponse(
        id=template.id,
        name=template.name,
        prompt=template.prompt,
        category=template.category,
        icon=template.icon,
        user_id=template.user_id,
        org_id=template.org_id,
        created_at=template.created_at,
        updated_at=template.updated_at,
    )


@router.get("/{template_id}", response_model=TemplateResponse)
async def get_template(
    current_user: CurrentUser,
    template_id: str,
    session: AsyncSession = Depends(get_session),
):
    """R\u00e9cup\u00e9rer un template par ID."""
    stmt = select(PromptTemplate).where(
        PromptTemplate.id == template_id,
        or_(
            PromptTemplate.user_id == current_user.id,
            (PromptTemplate.user_id.is_(None)) & (PromptTemplate.org_id == current_user.org_id),
        ),
    )
    result = await session.execute(stmt)
    template = result.scalar_one_or_none()

    if not template:
        raise HTTPException(status_code=404, detail="Template introuvable")

    return TemplateResponse(
        id=template.id,
        name=template.name,
        prompt=template.prompt,
        category=template.category,
        icon=template.icon,
        user_id=template.user_id,
        org_id=template.org_id,
        created_at=template.created_at,
        updated_at=template.updated_at,
    )


@router.put("/{template_id}", response_model=TemplateResponse)
async def update_template(
    current_user: CurrentUser,
    template_id: str,
    body: TemplateUpdate,
    session: AsyncSession = Depends(get_session),
):
    """Modifier un template (propri\u00e9taire uniquement)."""
    template = await get_owned(session, PromptTemplate, template_id, current_user)
    if not template:
        raise HTTPException(status_code=404, detail="Template introuvable ou acc\u00e8s refus\u00e9")

    if body.category is not None and body.category not in VALID_CATEGORIES:
        raise HTTPException(
            status_code=400,
            detail=f"Cat\u00e9gorie invalide. Valeurs possibles : {', '.join(sorted(VALID_CATEGORIES))}",
        )

    if body.name is not None:
        template.name = body.name
    if body.prompt is not None:
        template.prompt = body.prompt
    if body.category is not None:
        template.category = body.category
    if body.icon is not None:
        template.icon = body.icon

    template.updated_at = datetime.utcnow()
    session.add(template)
    await session.commit()
    await session.refresh(template)

    logger.info("Template modifi\u00e9 : %s (user=%s)", template.name, current_user.id)

    return TemplateResponse(
        id=template.id,
        name=template.name,
        prompt=template.prompt,
        category=template.category,
        icon=template.icon,
        user_id=template.user_id,
        org_id=template.org_id,
        created_at=template.created_at,
        updated_at=template.updated_at,
    )


@router.delete("/{template_id}", status_code=204)
async def delete_template(
    current_user: CurrentUser,
    template_id: str,
    session: AsyncSession = Depends(get_session),
):
    """Supprimer un template (propri\u00e9taire uniquement)."""
    template = await get_owned(session, PromptTemplate, template_id, current_user)
    if not template:
        raise HTTPException(status_code=404, detail="Template introuvable ou acc\u00e8s refus\u00e9")

    await session.delete(template)
    await session.commit()

    logger.info("Template supprim\u00e9 : %s (user=%s)", template_id, current_user.id)


@router.post("/seed", response_model=dict)
async def seed_templates(
    current_user: User = RequireAdmin,
    session: AsyncSession = Depends(get_session),
):
    """Initialiser les templates par d\u00e9faut pour l'organisation (admin uniquement).

    Ne cr\u00e9e rien si des templates org existent d\u00e9j\u00e0.
    """
    stmt = select(PromptTemplate).where(
        PromptTemplate.org_id == current_user.org_id,
        PromptTemplate.user_id.is_(None),
    )
    result = await session.execute(stmt)
    existing = result.scalars().all()

    if existing:
        return {
            "message": "Des templates existent d\u00e9j\u00e0 pour cette organisation",
            "count": len(existing),
            "created": 0,
        }

    created = 0
    for tpl_data in DEFAULT_TEMPLATES:
        template = PromptTemplate(
            name=tpl_data["name"],
            prompt=tpl_data["prompt"],
            category=tpl_data["category"],
            icon=tpl_data.get("icon"),
            user_id=None,
            org_id=current_user.org_id,
        )
        session.add(template)
        created += 1

    await session.commit()

    logger.info(
        "Seed templates : %d cr\u00e9\u00e9s pour org=%s (par user=%s)",
        created,
        current_user.org_id,
        current_user.id,
    )

    return {
        "message": f"{created} templates cr\u00e9\u00e9s pour l'organisation",
        "count": created,
        "created": created,
    }
