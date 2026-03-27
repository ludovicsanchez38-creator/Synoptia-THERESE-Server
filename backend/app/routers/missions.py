"""Router API pour les missions autonomes."""
import logging
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.rbac import CurrentUser
from app.models.database import get_session
from app.models.schemas_missions import (
    MissionPollResponse,
    MissionRequest,
    MissionResponse,
    MissionStartResponse,
    MissionTypeInfo,
)
from app.services.missions.service import (
    MISSION_TYPE_INFO,
    get_mission_service,
)

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/types", response_model=list[MissionTypeInfo])
async def list_mission_types():
    return MISSION_TYPE_INFO


@router.post("/start", response_model=MissionStartResponse)
async def start_mission(
    req: MissionRequest,
    current_user: CurrentUser,
    session: AsyncSession = Depends(get_session),
):
    svc = get_mission_service()
    try:
        mission = await svc.start_mission(
            session=session,
            mission_type=req.mission_type,
            input_text=req.input_text,
            user_id=current_user.id,
            org_id=current_user.org_id,
            conversation_id=req.conversation_id,
            title=req.title,
        )
        return MissionStartResponse(
            id=mission.id,
            status=mission.status,
            message=f"Mission lancée: {mission.title}",
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("", response_model=list[MissionResponse])
async def list_missions(
    current_user: CurrentUser,
    session: AsyncSession = Depends(get_session),
):
    svc = get_mission_service()
    missions = await svc.list_missions(session, current_user.id, current_user.org_id)
    return [
        MissionResponse(
            id=m.id,
            mission_type=m.mission_type,
            title=m.title,
            status=m.status,
            progress=m.progress,
            result_content=m.result_content,
            openclaw_agent=m.openclaw_agent,
            tokens_used=m.tokens_used,
            cost_eur=m.cost_eur,
            error=m.error,
            created_at=m.created_at,
            started_at=m.started_at,
            completed_at=m.completed_at,
        )
        for m in missions
    ]


@router.get("/{mission_id}", response_model=MissionResponse)
async def get_mission(
    mission_id: str,
    current_user: CurrentUser,
    session: AsyncSession = Depends(get_session),
):
    svc = get_mission_service()
    mission = await svc.get_mission(session, mission_id, current_user.id)
    if not mission:
        raise HTTPException(status_code=404, detail="Mission introuvable")
    return MissionResponse(
        id=mission.id,
        mission_type=mission.mission_type,
        title=mission.title,
        status=mission.status,
        progress=mission.progress,
        result_content=mission.result_content,
        openclaw_agent=mission.openclaw_agent,
        tokens_used=mission.tokens_used,
        cost_eur=mission.cost_eur,
        error=mission.error,
        created_at=mission.created_at,
        started_at=mission.started_at,
        completed_at=mission.completed_at,
    )


@router.get("/{mission_id}/poll", response_model=MissionPollResponse)
async def poll_mission(
    mission_id: str,
    current_user: CurrentUser,
    session: AsyncSession = Depends(get_session),
):
    svc = get_mission_service()
    mission = await svc.get_mission(session, mission_id, current_user.id)
    if not mission:
        raise HTTPException(status_code=404, detail="Mission introuvable")
    return MissionPollResponse(
        id=mission.id,
        status=mission.status,
        progress=mission.progress,
        result_content=mission.result_content,
        error=mission.error,
    )


@router.post("/{mission_id}/cancel")
async def cancel_mission(
    mission_id: str,
    current_user: CurrentUser,
    session: AsyncSession = Depends(get_session),
):
    svc = get_mission_service()
    mission = await svc.cancel_mission(session, mission_id, current_user.id)
    if not mission:
        raise HTTPException(status_code=404, detail="Mission introuvable")
    return {"status": mission.status, "message": "Mission annulée"}
