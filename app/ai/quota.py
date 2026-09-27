"""Per-user daily AI-call quota, checked before cache lookup or any provider
call. See ai-architecture.md section 8."""
from __future__ import annotations

from datetime import UTC, datetime

from redis.asyncio import Redis

DEFAULT_DAILY_LIMITS = {
    "match_scoring": 50,
    "cv_tailoring": 10,
    "message_generation": 20,
}


class QuotaExceededError(Exception):
    def __init__(self, action: str, limit: int) -> None:
        self.action = action
        self.limit = limit
        super().__init__(f"Daily limit of {limit} for '{action}' reached; resets at midnight UTC.")


class AIQuota:
    def __init__(self, redis: Redis, limits: dict[str, int] | None = None) -> None:
        self._redis = redis
        self._limits = limits or DEFAULT_DAILY_LIMITS

    def _key(self, user_id: str, action: str) -> str:
        today = datetime.now(UTC).strftime("%Y-%m-%d")
        return f"ai_quota:{user_id}:{action}:{today}"

    async def check_and_increment(self, user_id: str, action: str, amount: int = 1) -> None:
        limit = self._limits.get(action)
        if limit is None:
            return  # unmetered action

        key = self._key(user_id, action)
        current = await self._redis.get(key)
        current_count = int(current) if current else 0
        if current_count + amount > limit:
            raise QuotaExceededError(action, limit)

        pipe = self._redis.pipeline()
        pipe.incrby(key, amount)
        pipe.expire(key, 86400)  # safety TTL; key also naturally rotates by date
        await pipe.execute()
