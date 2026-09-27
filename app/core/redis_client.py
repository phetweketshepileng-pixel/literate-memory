"""Async Redis client — a single shared connection pool reused across the
app and Celery workers. Cache and broker are separate logical databases
per the V1.1 review's Redis-separation fix."""
from __future__ import annotations

from redis.asyncio import Redis

from app.core.config import settings

_redis_client: Redis | None = None


async def get_redis() -> Redis:
    global _redis_client
    if _redis_client is None:
        _redis_client = Redis.from_url(settings.REDIS_CACHE_URL, decode_responses=False)
    return _redis_client
