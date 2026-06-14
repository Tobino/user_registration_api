"""In-memory test doubles for the service collaborators."""

from __future__ import annotations

from uuid import uuid4

from app.repositories.user_repository import UserRecord


class FakeUserRepository:
    """Stores created users in a dict instead of hitting Postgres."""

    def __init__(self) -> None:
        self.by_email: dict[str, UserRecord] = {}

    async def create(self, email: str, password_hash: str) -> UserRecord | None:
        if email in self.by_email:
            return None
        record = UserRecord(
            id=uuid4(), email=email, password_hash=password_hash, is_active=False
        )
        self.by_email[email] = record
        return record


class FakeEmailSender:
    """Records every activation code it is asked to send instead of doing HTTP."""

    def __init__(self) -> None:
        self.sent: list[tuple[str, str]] = []

    async def send_activation_code(self, email: str, code: str) -> None:
        self.sent.append((email, code))
