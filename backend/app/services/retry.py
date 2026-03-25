"""
THÉRÈSE Server - Retry avec backoff exponentiel et circuit breaker.

Usage :
    async for event in retry_stream(provider.stream, system, msgs, tools):
        yield event
"""

import asyncio
import logging
import time
from collections.abc import AsyncGenerator, Callable
from typing import Any, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


class CircuitBreaker:
    """Circuit breaker simple pour les providers LLM."""

    def __init__(self, failure_threshold: int = 3, recovery_timeout: float = 60.0):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self._failure_count = 0
        self._last_failure_time: float = 0
        self._state = "closed"  # closed, open, half-open

    @property
    def is_open(self) -> bool:
        if self._state == "open":
            if time.monotonic() - self._last_failure_time > self.recovery_timeout:
                self._state = "half-open"
                return False
            return True
        return False

    def record_success(self) -> None:
        self._failure_count = 0
        self._state = "closed"

    def record_failure(self) -> None:
        self._failure_count += 1
        self._last_failure_time = time.monotonic()
        if self._failure_count >= self.failure_threshold:
            self._state = "open"
            logger.warning(
                "Circuit breaker ouvert apres %d echecs (recovery dans %ds)",
                self._failure_count,
                self.recovery_timeout,
            )


# Un circuit breaker par provider
_breakers: dict[str, CircuitBreaker] = {}


def get_breaker(provider_name: str) -> CircuitBreaker:
    if provider_name not in _breakers:
        _breakers[provider_name] = CircuitBreaker()
    return _breakers[provider_name]


async def retry_stream(
    stream_fn: Callable[..., AsyncGenerator[T, None]],
    *args: Any,
    max_retries: int = 2,
    base_delay: float = 1.0,
    provider_name: str = "unknown",
    **kwargs: Any,
) -> AsyncGenerator[T, None]:
    """Retry un generateur async avec backoff exponentiel.

    Si le circuit breaker est ouvert, leve immediatement une erreur.
    """
    breaker = get_breaker(provider_name)

    if breaker.is_open:
        raise RuntimeError(f"Circuit breaker ouvert pour {provider_name} - reessayez dans quelques secondes")

    last_error: BaseException | None = None

    for attempt in range(max_retries + 1):
        try:
            async for event in stream_fn(*args, **kwargs):
                yield event
            breaker.record_success()
            return
        except (OSError, RuntimeError, TimeoutError) as e:
            last_error = e
            breaker.record_failure()
            if attempt < max_retries:
                delay = base_delay * (2 ** attempt)
                logger.warning(
                    "Retry %d/%d pour %s apres erreur : %s (delai %.1fs)",
                    attempt + 1,
                    max_retries,
                    provider_name,
                    str(e)[:100],
                    delay,
                )
                await asyncio.sleep(delay)
            else:
                logger.error("Echec definitif pour %s apres %d tentatives", provider_name, max_retries + 1)

    if last_error:
        raise last_error
