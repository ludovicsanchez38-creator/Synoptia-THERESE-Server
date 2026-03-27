"""OpenClaw runner - lance des agents via le bridge HTTP."""
import asyncio
import logging
import os

import httpx

logger = logging.getLogger(__name__)

BRIDGE_URL = os.getenv("OPENCLAW_BRIDGE_URL", "http://172.18.0.1:18800")


class OpenClawRunner:
    """Lance un agent OpenClaw via le bridge HTTP."""

    async def run_agent(
        self,
        agent_name: str,
        prompt: str,
        timeout: int = 300,
    ) -> tuple[str, int]:
        """Appelle le bridge OpenClaw et retourne (output, exit_code)."""
        logger.info("Lancement agent OpenClaw: %s via %s (timeout=%ds)", agent_name, BRIDGE_URL, timeout)

        try:
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(timeout + 30, connect=10)
            ) as client:
                resp = await client.post(
                    BRIDGE_URL,
                    json={
                        "agent": agent_name,
                        "message": prompt,
                        "timeout": timeout,
                    },
                )

                if resp.status_code == 200:
                    data = resp.json()
                    output = data.get("output", "")
                    exit_code = data.get("exit_code", 0)

                    if data.get("error") == "timeout":
                        return "", -1

                    if not output and data.get("error"):
                        output = data["error"]

                    return output, exit_code
                else:
                    return f"Erreur bridge HTTP {resp.status_code}: {resp.text[:300]}", -3

        except httpx.TimeoutException:
            logger.warning("Agent %s timeout HTTP apres %ds", agent_name, timeout)
            return "", -1
        except httpx.ConnectError as e:
            logger.error("Impossible de joindre le bridge OpenClaw: %s", e)
            return f"Erreur: bridge OpenClaw inaccessible ({BRIDGE_URL}). Verifiez que openclaw-bridge.py tourne.", -2
        except Exception as e:
            logger.error("Erreur inattendue agent %s: %s", agent_name, e)
            return f"Erreur: {e}", -3
