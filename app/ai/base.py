"""
AIProvider — the single interface every module calls through. Never call an
LLM SDK directly from a module's service layer; go through this so provider
swaps, retries, timeouts, and circuit breaking are consistent everywhere.
See docs/ai-architecture.md sections 1-2, 7.1-7.2.
"""
from __future__ import annotations

import abc
import asyncio
import random
from dataclasses import dataclass
from typing import Any

from app.ai.circuit_breaker import CircuitBreaker, CircuitOpenError


class AIProviderError(Exception):
    """Raised after all retries are exhausted or the circuit is open.
    Callers should catch this specifically and invoke their module's
    fallback path (never let it propagate as a 500 to the user)."""


@dataclass
class AICompletionResult:
    content: str                 # raw text/JSON returned by the model
    prompt_tokens: int
    completion_tokens: int
    model: str


class AIProvider(abc.ABC):
    """Abstract base — implement `_call` per provider; everything else
    (timeout, retry/backoff, circuit breaking) is shared here so every
    provider gets the same resilience behavior for free."""

    name: str

    def __init__(
        self,
        circuit_breaker: CircuitBreaker,
        timeout_seconds: float = 20.0,
        max_retries: int = 3,
        base_backoff_seconds: float = 1.0,
    ) -> None:
        self._circuit_breaker = circuit_breaker
        self._timeout_seconds = timeout_seconds
        self._max_retries = max_retries
        self._base_backoff_seconds = base_backoff_seconds

    @abc.abstractmethod
    async def _call(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        json_schema: dict[str, Any] | None,
        max_tokens: int,
        model: str,
    ) -> AICompletionResult:
        """Provider-specific implementation. Must raise on failure (timeout,
        5xx, rate limit) rather than returning a partial/empty result, so the
        retry loop in `complete()` can act on it."""

    async def complete(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        json_schema: dict[str, Any] | None = None,
        max_tokens: int = 800,
        model: str = "default",
    ) -> AICompletionResult:
        """Retry policy: up to `max_retries` attempts with exponential
        backoff + jitter, only for retriable failures. The circuit breaker
        is checked before every attempt and updated after every outcome."""
        last_error: Exception | None = None

        for attempt in range(self._max_retries):
            try:
                await self._circuit_breaker.before_call()
            except CircuitOpenError as exc:
                raise AIProviderError(str(exc)) from exc

            try:
                result = await asyncio.wait_for(
                    self._call(
                        system_prompt=system_prompt,
                        user_prompt=user_prompt,
                        json_schema=json_schema,
                        max_tokens=max_tokens,
                        model=model,
                    ),
                    timeout=self._timeout_seconds,
                )
                await self._circuit_breaker.record_success()
                return result
            except asyncio.TimeoutError as exc:
                last_error = exc
                await self._circuit_breaker.record_failure()
            except _RetriableProviderError as exc:
                last_error = exc
                await self._circuit_breaker.record_failure()
            except _NonRetriableProviderError as exc:
                # A validation/schema error — retrying the identical prompt
                # won't fix it, so fail straight to the caller's fallback.
                raise AIProviderError(str(exc)) from exc

            if attempt < self._max_retries - 1:
                backoff = self._base_backoff_seconds * (2 ** attempt)
                backoff += random.uniform(0, backoff * 0.25)  # jitter
                await asyncio.sleep(backoff)

        raise AIProviderError(
            f"Exhausted {self._max_retries} attempts against {self.name}: {last_error}"
        )


class _RetriableProviderError(Exception):
    """Provider implementations raise this for timeouts, 5xx, rate limits."""


class _NonRetriableProviderError(Exception):
    """Provider implementations raise this for 4xx/validation errors."""
