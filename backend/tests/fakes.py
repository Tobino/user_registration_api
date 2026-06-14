"""In-memory test doubles for the service collaborators."""

from __future__ import annotations

from dataclasses import replace
from uuid import UUID, uuid4

from app.repositories.user_repository import UserRecord


class FakeUserRepository:
    """Stores created users in a dict instead of hitting Postgres."""

    def __init__(self) -> None:
        self.by_email: dict[str, UserRecord] = {}

    async def get_by_email(self, email: str) -> UserRecord | None:
        return self.by_email.get(email)

    async def create(self, email: str, password_hash: str) -> UserRecord | None:
        if email in self.by_email:
            return None
        record = UserRecord(
            id=uuid4(), email=email, password_hash=password_hash, is_active=False
        )
        self.by_email[email] = record
        return record

    async def update_password(self, user_id: UUID, password_hash: str) -> None:
        for email, record in self.by_email.items():
            if record.id == user_id:
                self.by_email[email] = replace(record, password_hash=password_hash)
                return

    async def mark_active(self, user_id: UUID) -> None:
        for email, record in self.by_email.items():
            if record.id == user_id:
                self.by_email[email] = replace(record, is_active=True)
                return


class FakeCodeStore:
    """Stores activation codes (and failed-attempt counts) in dicts."""

    def __init__(self) -> None:
        self.codes: dict[str, str] = {}
        self.attempts: dict[str, int] = {}
        self.refreshed: list[str] = []

    async def store(self, email: str, code: str) -> None:
        # A new code resets the attempt budget, mirroring the real store.
        self.attempts.pop(email, None)
        self.codes[email] = code

    async def refresh(self, email: str) -> None:
        # No real TTL in the fake; mirror Redis EXPIRE's no-op on a missing key.
        self.refreshed.append(email)

    async def get(self, email: str) -> str | None:
        return self.codes.get(email)

    async def get_attempts(self, email: str) -> int:
        return self.attempts.get(email, 0)

    async def record_failed_attempt(self, email: str) -> int:
        self.attempts[email] = self.attempts.get(email, 0) + 1
        return self.attempts[email]

    async def delete(self, email: str) -> None:
        self.codes.pop(email, None)
        self.attempts.pop(email, None)


class FakeEmailSender:
    """Records every activation code it is asked to send instead of doing HTTP."""

    def __init__(self) -> None:
        self.sent: list[tuple[str, str]] = []

    async def send_activation_code(self, email: str, code: str) -> None:
        self.sent.append((email, code))
