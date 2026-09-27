"""Per-source token bucket rate limiter — architecture doc section 7.
Enforced independently of Celery concurrency, so scaling worker count
never accidentally exceeds a source's documented rate limit."""
from __future__ import annotations

import time

from redis.asyncio import Redis


class RateLimitExceeded(Exception):
    pass


class TokenBucketLimiter:
    """Simple fixed-window limiter: `rate_per_minute` tokens refill every
    60 seconds. Sufficient for the polling cadences in the architecture doc
    (measured in requests per minute, not per second); a sliding-window
    implementation would be overkill here."""

    def __init__(self, redis: Redis, key: str, rate_per_minute: int) -> None:
        self._redis = redis
        self._key = key
        self._rate_per_minute = rate_per_minute

    async def acquire(self) -> None:
        window = int(time.time() // 60)
        window_key = f"{self._key}:{window}"

        count = await self._redis.incr(window_key)
        if count == 1:
            await self._redis.expire(window_key, 65)

        if count > self._rate_per_minute:
            raise RateLimitExceeded(
                f"Rate limit exceeded for {self._key}: {count} > {self._rate_per_minute}/min"
            )
