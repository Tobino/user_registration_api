"""Activation-code storage in Redis.

The code lives under a per-email key with a TTL equal to the configured
validity window (60s), so expiry is enforced by Redis itself — once the key is
gone the code is simply unusable.
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

    async def store(self, email: str, code: str) -> None:
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

    async def delete(self, email: str) -> None:
        await self._redis.delete(self._key(email))
