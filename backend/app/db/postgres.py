"""PostgreSQL access through an asyncpg connection pool.

The pool is exposed directly so the application can issue raw,
parameterised SQL. This module owns the pool lifecycle (open on startup, close
on shutdown).
"""

from __future__ import annotations

import logging

import asyncpg

logger = logging.getLogger(__name__)


class Database:
    """Thin wrapper around an :class:`asyncpg.Pool`."""

    def __init__(self, dsn: str, *, min_size: int = 1, max_size: int = 10) -> None:
        self._dsn = dsn
        self._min_size = min_size
        self._max_size = max_size
        self._pool: asyncpg.Pool | None = None

    @property
    def pool(self) -> asyncpg.Pool:
        if self._pool is None:
            raise RuntimeError("Database pool is not initialised. Call connect() first.")
        return self._pool

    async def connect(self) -> None:
        self._pool = await asyncpg.create_pool(
            dsn=self._dsn,
            min_size=self._min_size,
            max_size=self._max_size,
        )
        logger.info("PostgreSQL pool established")

    async def disconnect(self) -> None:
        if self._pool is not None:
            await self._pool.close()
            self._pool = None
            logger.info("PostgreSQL pool closed")
