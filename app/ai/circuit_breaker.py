"""Circuit breaker for AI provider calls, backed by Redis so state is shared
across Celery worker processes. See docs/ai-architecture.md section 7.1.
"""
from __future__ import annotations

import time
from enum import Enum

from redis.asyncio import Redis


class CircuitState(str, Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitOpenError(Exception):
    """Raised when a call is attempted while the circuit is open."""


class CircuitBreaker:
    """
    Rolling-window failure-rate circuit breaker.

    - CLOSED: calls proceed normally.
    - OPEN: calls fail fast (CircuitOpenError) until `cooldown_seconds` elapses.
    - HALF_OPEN: a limited number of probe calls are allowed through; a single
      success closes the circuit, a single failure reopens it for another
      full cooldown period.
    """

    def __init__(
        self,
        redis: Redis,
        provider_name: str,
        failure_threshold: int = 5,
        window_seconds: int = 120,
        cooldown_seconds: int = 60,
        half_open_max_probes: int = 1,
    ) -> None:
        self._redis = redis
        self._key_prefix = f"circuit:{provider_name}"
        self._failure_threshold = failure_threshold
        self._window_seconds = window_seconds
        self._cooldown_seconds = cooldown_seconds
        self._half_open_max_probes = half_open_max_probes

    @property
    def _state_key(self) -> str:
        return f"{self._key_prefix}:state"

    @property
    def _opened_at_key(self) -> str:
        return f"{self._key_prefix}:opened_at"

    @property
    def _failures_key(self) -> str:
        return f"{self._key_prefix}:failures"

    @property
    def _probes_key(self) -> str:
        return f"{self._key_prefix}:probes"

    async def _get_state(self) -> CircuitState:
        raw = await self._redis.get(self._state_key)
        if raw is None:
            return CircuitState.CLOSED
        state = CircuitState(raw.decode() if isinstance(raw, bytes) else raw)
        if state == CircuitState.OPEN:
            opened_at = await self._redis.get(self._opened_at_key)
            if opened_at and (time.time() - float(opened_at)) >= self._cooldown_seconds:
                await self._redis.set(self._state_key, CircuitState.HALF_OPEN.value)
                await self._redis.delete(self._probes_key)
                return CircuitState.HALF_OPEN
        return state

    async def before_call(self) -> None:
        state = await self._get_state()
        if state == CircuitState.OPEN:
            raise CircuitOpenError("Circuit is open; failing fast to fallback path.")
        if state == CircuitState.HALF_OPEN:
            probes = await self._redis.incr(self._probes_key)
            if probes > self._half_open_max_probes:
                raise CircuitOpenError("Half-open probe budget exhausted; failing fast.")

    async def record_success(self) -> None:
        state = await self._get_state()
        if state == CircuitState.HALF_OPEN:
            await self._redis.set(self._state_key, CircuitState.CLOSED.value)
            await self._redis.delete(self._failures_key)
        else:
            # sliding-window failure counter reset on any success in CLOSED state
            await self._redis.delete(self._failures_key)

    async def record_failure(self) -> None:
        state = await self._get_state()
        if state == CircuitState.HALF_OPEN:
            await self._open()
            return

        failures = await self._redis.incr(self._failures_key)
        if failures == 1:
            await self._redis.expire(self._failures_key, self._window_seconds)
        if failures >= self._failure_threshold:
            await self._open()

    async def _open(self) -> None:
        await self._redis.set(self._state_key, CircuitState.OPEN.value)
        await self._redis.set(self._opened_at_key, str(time.time()))
        await self._redis.delete(self._failures_key)
        await self._redis.delete(self._probes_key)
