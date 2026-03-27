"""Service de gestion des missions autonomes."""
import asyncio
import logging
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.models.entities_missions import Mission, MissionStatus, MissionType
from app.services.missions.openclaw_runner import OpenClawRunner

logger = logging.getLogger(__name__)

AGENT_MAP = {
    MissionType.CONFORMITY.value: "agent-conformite",
    MissionType.RESEARCH.value: "agent-recherche",
    MissionType.DOCUMENT.value: "agent-redaction",
    MissionType.CRM.value: "agent-crm",
}

MISSION_TYPE_INFO = [
    {
        "type": MissionType.CONFORMITY.value,
        "label": "Vérificateur de conformité",
        "description": "Analyse un document au regard du CGCT et de la réglementation applicable",
        "icon": "shield-check",
    },
]

# Semaphores par org pour limiter la concurrence
_org_semaphores: dict[str, asyncio.Semaphore] = {}
_running_tasks: dict[str, asyncio.Task] = {}

DEFAULT_MAX_CONCURRENT = 3
DEFAULT_TIMEOUT = 300


def _get_org_semaphore(org_id: str, max_concurrent: int = DEFAULT_MAX_CONCURRENT) -> asyncio.Semaphore:
    if org_id not in _org_semaphores:
        _org_semaphores[org_id] = asyncio.Semaphore(max_concurrent)
    return _org_semaphores[org_id]


class MissionService:
    def __init__(self):
        self.runner = OpenClawRunner()

    async def start_mission(
        self,
        session: AsyncSession,
        mission_type: str,
        input_text: str,
        user_id: str,
        org_id: str,
        conversation_id: str | None = None,
        title: str | None = None,
    ) -> Mission:
        agent_name = AGENT_MAP.get(mission_type)
        if not agent_name:
            raise ValueError(f"Type de mission inconnu: {mission_type}")

        # Vérifier limites concurrence
        stmt = select(Mission).where(
            Mission.org_id == org_id,
            Mission.status == MissionStatus.RUNNING.value,
        )
        result = await session.execute(stmt)
        running = len(result.all())
        if running >= DEFAULT_MAX_CONCURRENT:
            raise ValueError(
                f"Limite atteinte: {running}/{DEFAULT_MAX_CONCURRENT} missions en cours pour cette organisation"
            )

        mission = Mission(
            user_id=user_id,
            org_id=org_id,
            conversation_id=conversation_id,
            mission_type=mission_type,
            title=title or f"Mission {mission_type}",
            input_text=input_text,
            openclaw_agent=agent_name,
            status=MissionStatus.PENDING.value,
        )
        session.add(mission)
        await session.commit()
        await session.refresh(mission)

        # Lancer en arrière-plan
        task = asyncio.create_task(self._run_mission(mission.id, agent_name, input_text, org_id))
        _running_tasks[mission.id] = task

        return mission

    async def _run_mission(self, mission_id: str, agent_name: str, prompt: str, org_id: str):
        from app.models.database import get_session_context

        sem = _get_org_semaphore(org_id)

        async with sem:
            async with get_session_context() as session:
                mission = await session.get(Mission, mission_id)
                if not mission or mission.status == MissionStatus.CANCELLED.value:
                    return

                mission.status = MissionStatus.RUNNING.value
                mission.started_at = datetime.utcnow()
                mission.progress = 10
                await session.commit()

            try:
                output, exit_code = await self.runner.run_agent(
                    agent_name, prompt, timeout=DEFAULT_TIMEOUT
                )

                async with get_session_context() as session:
                    mission = await session.get(Mission, mission_id)
                    if not mission:
                        return

                    if exit_code == -1:
                        mission.status = MissionStatus.TIMEOUT.value
                        mission.error = f"Timeout après {DEFAULT_TIMEOUT}s"
                    elif exit_code < 0:
                        mission.status = MissionStatus.FAILED.value
                        mission.error = output or f"Erreur système (code {exit_code})"
                    elif exit_code != 0:
                        mission.status = MissionStatus.FAILED.value
                        mission.error = output[:1000] if output else f"Code de sortie {exit_code}"
                        mission.result_content = output
                    else:
                        mission.status = MissionStatus.COMPLETED.value
                        mission.result_content = output

                    mission.progress = 100
                    mission.completed_at = datetime.utcnow()
                    await session.commit()

            except Exception as e:
                logger.exception("Erreur mission %s: %s", mission_id, e)
                async with get_session_context() as session:
                    mission = await session.get(Mission, mission_id)
                    if mission:
                        mission.status = MissionStatus.FAILED.value
                        mission.error = str(e)[:1000]
                        mission.completed_at = datetime.utcnow()
                        mission.progress = 100
                        await session.commit()
            finally:
                _running_tasks.pop(mission_id, None)

    async def cancel_mission(self, session: AsyncSession, mission_id: str, user_id: str) -> Mission | None:
        mission = await session.get(Mission, mission_id)
        if not mission or mission.user_id != user_id:
            return None
        if mission.status not in (MissionStatus.PENDING.value, MissionStatus.RUNNING.value):
            return mission

        mission.status = MissionStatus.CANCELLED.value
        mission.completed_at = datetime.utcnow()
        mission.progress = 100
        await session.commit()

        task = _running_tasks.pop(mission_id, None)
        if task and not task.done():
            task.cancel()

        return mission

    async def list_missions(
        self, session: AsyncSession, user_id: str, org_id: str, limit: int = 50
    ) -> list[Mission]:
        stmt = (
            select(Mission)
            .where(Mission.user_id == user_id, Mission.org_id == org_id)
            .order_by(Mission.created_at.desc())
            .limit(limit)
        )
        result = await session.execute(stmt)
        return list(result.scalars().all())

    async def get_mission(self, session: AsyncSession, mission_id: str, user_id: str) -> Mission | None:
        mission = await session.get(Mission, mission_id)
        if mission and mission.user_id == user_id:
            return mission
        return None


_mission_service: MissionService | None = None


def get_mission_service() -> MissionService:
    global _mission_service
    if _mission_service is None:
        _mission_service = MissionService()
    return _mission_service
