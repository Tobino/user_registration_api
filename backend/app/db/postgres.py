"""PostgreSQL access through an asyncpg connection pool.

The pool is exposed directly so the application can issue raw,
parameterised SQL. This module owns the pool lifecycle (open on startup, close
on shutdown) and applies the ``.sql`` migrations on startup so a fresh container
is usable immediately.
"""

from __future__ import annotations

import logging
from pathlib import Path

import asyncpg

logger = logging.getLogger(__name__)

_MIGRATIONS_DIR = Path(__file__).parent / "migrations"


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

    async def apply_migrations(self) -> None:
        """Run every ``*.sql`` file in lexical order, each in its own transaction.

        Migrations are written to be idempotent (``CREATE TABLE IF NOT EXISTS``),
        which keeps startup simple without a full migration-tracking table.
        """
        files = sorted(_MIGRATIONS_DIR.glob("*.sql"))
        async with self.pool.acquire() as conn:
            for path in files:
                sql = path.read_text(encoding="utf-8")
                async with conn.transaction():
                    await conn.execute(sql)
                logger.info("Applied migration %s", path.name)
