"""get_or_compute cache wrapper for AI results. See ai-architecture.md
section 6 for the key/TTL scheme per module."""
from __future__ import annotations

import hashlib
import json
from collections.abc import Awaitable, Callable
from typing import TypeVar

from redis.asyncio import Redis

T = TypeVar("T")


def content_hash(*parts: str) -> str:
    """Stable short hash used to embed content-sensitivity into cache keys
    (e.g. profile_updated_at, job content) so stale entries are simply
    never matched again rather than requiring explicit invalidation."""
    joined = "|".join(parts)
    return hashlib.sha256(joined.encode()).hexdigest()[:16]


class AIResultCache:
    def __init__(self, redis: Redis) -> None:
        self._redis = redis

    async def get_or_compute(
        self,
        key: str,
        compute: Callable[[], Awaitable[dict]],
        ttl_seconds: int,
    ) -> dict:
        cached = await self._redis.get(key)
        if cached is not None:
            return json.loads(cached)

        result = await compute()
        await self._redis.set(key, json.dumps(result), ex=ttl_seconds)
        return result

    @staticmethod
    def match_key(profile_id: str, job_id: str, profile_updated_at: str, job_content_hash: str) -> str:
        return f"match:{profile_id}:{job_id}:{content_hash(profile_updated_at, job_content_hash)}"

    @staticmethod
    def keyword_key(job_id: str, job_content_hash: str) -> str:
        return f"keywords:{job_id}:{job_content_hash}"

    @staticmethod
    def skill_course_map_key(skill_name_normalized: str) -> str:
        return f"skill_course_map:{skill_name_normalized}"
