"""Redis-backed sliding-window rate limiting.

:class:`RateLimiter` is a generic timestamp sliding window built on a Redis
sorted set (members scored by epoch seconds). The policy classes apply it to the
product rules and raise :class:`~app.core.exceptions.RateLimitExceeded` when a
limit is hit:

* :class:`RegistrationRateLimiter` — at most N account registrations per client
  identity within a rolling window (default: 50 per hour);
* :class:`EmailRateLimiter` — at most N activation-code emails per address,
  enforced across two rolling windows at once (default: 3 per hour and 10 per
  day), mitigating email-bombing via the resend path.
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


class EmailRateLimiter:
    """Caps activation-code emails per address across two rolling windows.

    Both the initial send and every resend count toward the budget. The two
    windows are checked *before* recording, so a hit blocked by one window never
    leaves a phantom entry in the other.
    """

    _HOUR_SECONDS = 3600
    _DAY_SECONDS = 86_400

    def __init__(
        self, limiter: RateLimiter, *, hourly_limit: int, daily_limit: int
    ) -> None:
        self._limiter = limiter
        self._hourly_limit = hourly_limit
        self._daily_limit = daily_limit

    @staticmethod
    def _hour_key(email: str) -> str:
        return f"ratelimit:email-send-hour:{email}"

    @staticmethod
    def _day_key(email: str) -> str:
        return f"ratelimit:email-send-day:{email}"

    async def enforce(self, email: str) -> None:
        """Raise if this address already hit its hourly or daily email budget."""
        hour_count = await self._limiter.count(
            self._hour_key(email), window_seconds=self._HOUR_SECONDS
        )
        if hour_count >= self._hourly_limit:
            raise RateLimitExceeded(
                "Too many activation emails for this address this hour. "
                "Try again later.",
                retry_after=self._HOUR_SECONDS,
            )

        day_count = await self._limiter.count(
            self._day_key(email), window_seconds=self._DAY_SECONDS
        )
        if day_count >= self._daily_limit:
            raise RateLimitExceeded(
                "Too many activation emails for this address today. "
                "Try again later.",
                retry_after=self._DAY_SECONDS,
            )

        # Both windows have headroom -> record the send in each.
        await self._limiter.record(
            self._hour_key(email), window_seconds=self._HOUR_SECONDS
        )
        await self._limiter.record(
            self._day_key(email), window_seconds=self._DAY_SECONDS
        )
