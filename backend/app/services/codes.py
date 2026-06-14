"""Activation-code storage in Redis.

The code lives under a per-email key with a TTL equal to the configured
validity window (60s), so expiry is enforced by Redis itself — once the key is
gone the code is simply unusable.

Alongside the code we track the number of failed activation attempts under a
sibling key so the service can enforce a 3-attempt cap. The counter shares the
code's TTL and is cleared whenever a fresh code is issued or a code is consumed,
so each new code grants a fresh attempt budget.
"""

from __future__ import annotations

import redis.asyncio as redis


class CodeStore:
    def __init__(self, client: redis.Redis, ttl_seconds: int) -> None:
        self._redis = client
        self._ttl = ttl_seconds

    @staticmethod
    def _key(email: str) -> str:
        return f"activation:code:{email}"

    @staticmethod
    def _attempts_key(email: str) -> str:
        return f"activation:attempts:{email}"

    async def store(self, email: str, code: str) -> None:
        # A new code resets the attempt budget so the user gets a fresh 3 tries.
        await self._redis.delete(self._attempts_key(email))
        await self._redis.set(self._key(email), code, ex=self._ttl)

    async def refresh(self, email: str) -> None:
        """Reset the validity window to the full TTL without touching the code.

        Called once the (potentially slow) email send has completed so the user
        gets the full window from delivery, not from when the code was stored.
        Redis ``EXPIRE`` is a no-op if the key has already expired.
        """
        await self._redis.expire(self._key(email), self._ttl)

    async def get(self, email: str) -> str | None:
        return await self._redis.get(self._key(email))

    async def get_attempts(self, email: str) -> int:
        """Number of failed activation attempts recorded for the current code."""
        value = await self._redis.get(self._attempts_key(email))
        return int(value) if value is not None else 0

    async def record_failed_attempt(self, email: str) -> int:
        """Increment and return the failed-attempt counter.

        The counter is bounded to the code's validity window via ``EXPIRE`` so a
        stale lockout can never outlive the code it guards.
        """
        key = self._attempts_key(email)
        count = await self._redis.incr(key)
        await self._redis.expire(key, self._ttl)
        return int(count)

    async def delete(self, email: str) -> None:
        await self._redis.delete(self._key(email), self._attempts_key(email))
