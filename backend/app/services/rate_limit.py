"""Redis-backed sliding-window rate limiting.

:class:`RateLimiter` is a generic timestamp sliding window built on a Redis
sorted set (members scored by epoch seconds). :class:`RegistrationRateLimiter`
applies it to the product rule and raises
:class:`~app.core.exceptions.RateLimitExceeded` when the limit is hit:

* at most ``limit`` account registrations per client IP within a rolling
  ``window_seconds`` window (defaults: 50 per hour).
"""

from __future__ import annotations

import time
from uuid import uuid4

import redis.asyncio as redis

from app.core.exceptions import RateLimitExceeded


class RateLimiter:
    def __init__(self, client: redis.Redis) -> None:
        self._redis = client

    @staticmethod
    def _now() -> float:
        return time.time()

    async def count(self, key: str, *, window_seconds: int) -> int:
        """Number of hits recorded within the trailing window (prunes old ones)."""
        now = self._now()
        async with self._redis.pipeline(transaction=True) as pipe:
            pipe.zremrangebyscore(key, "-inf", now - window_seconds)
            pipe.zcard(key)
            results = await pipe.execute()
        return int(results[1])

    async def record(self, key: str, *, window_seconds: int) -> None:
        """Record a single hit and refresh the key's TTL."""
        now = self._now()
        member = f"{now}-{uuid4().hex}"
        async with self._redis.pipeline(transaction=True) as pipe:
            pipe.zadd(key, {member: now})
            pipe.expire(key, window_seconds)
            await pipe.execute()

    async def allow(self, key: str, *, limit: int, window_seconds: int) -> bool:
        """Return True (and record a hit) if under ``limit``; False otherwise."""
        if await self.count(key, window_seconds=window_seconds) >= limit:
            return False
        await self.record(key, window_seconds=window_seconds)
        return True


class RegistrationRateLimiter:
    """Caps account registrations per client IP within a rolling window."""

    def __init__(
        self, limiter: RateLimiter, *, limit: int, window_seconds: int
    ) -> None:
        self._limiter = limiter
        self._limit = limit
        self._window_seconds = window_seconds

    @staticmethod
    def _key(ip: str) -> str:
        return f"ratelimit:signup-ip:{ip}"

    async def enforce(self, ip: str) -> None:
        """Record this attempt and raise once the per-IP budget is exhausted."""
        allowed = await self._limiter.allow(
            self._key(ip),
            limit=self._limit,
            window_seconds=self._window_seconds,
        )
        if not allowed:
            raise RateLimitExceeded(
                "Too many registrations from this IP. Try again later.",
                retry_after=self._window_seconds,
            )
