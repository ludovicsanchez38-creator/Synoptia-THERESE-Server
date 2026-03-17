"""
THÉRÈSE v2 - Agent System

Runtime embarqué pour les agents IA Thérèse (PM/Guide) et Zézette (Dev).
Format compatible OpenClaw (agent.json + SOUL.md).
"""

from app.services.agents.config import AgentConfig, load_agent_config
from app.services.agents.runtime import AgentRuntime

__all__ = [
    "AgentConfig",
    "AgentRuntime",
    "load_agent_config",
]
