"""Data-access layer for users — raw, parameterised SQL over asyncpg.

No ORM: every query is explicit. The repository returns plain
:class:`UserRecord` value objects so the rest of the app never depends on
asyncpg types.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

import asyncpg


@dataclass(frozen=True)
class UserRecord:
    id: UUID
    email: str
    password_hash: str
    is_active: bool


class UserRepository:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def create(self, email: str, password_hash: str) -> UserRecord | None:
        """Insert a new user with an already-hashed password.

        Uses ``ON CONFLICT DO NOTHING`` so a concurrent duplicate registration
        returns ``None`` instead of raising — the caller treats that as
        "already exists".
        """
        row = await self._pool.fetchrow(
            """
            INSERT INTO users (email, password_hash)
            VALUES ($1, $2)
            ON CONFLICT (email) DO NOTHING
            RETURNING id, email, password_hash, is_active
            """,
            email,
            password_hash,
        )
        return UserRecord(**dict(row)) if row is not None else None
