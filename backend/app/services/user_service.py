"""User registration/activation business logic.

It orchestrates the repository, the Redis-backed code store, and the email
sender, and raises :class:`~app.core.exceptions.DomainError` subclasses that the
API turns into HTTP responses.
"""

from __future__ import annotations

import secrets

from app.core.exceptions import (
    InvalidCredentials,
    InvalidOrExpiredCode,
    TooManyAttempts,
)
from app.core.security import generate_code, hash_password, verify_password
from app.repositories.user_repository import UserRepository
from app.services.codes import CodeStore
from app.services.email import EmailSender


class UserService:
    def __init__(
        self,
        users: UserRepository,
        codes: CodeStore,
        email: EmailSender,
        *,
        code_length: int = 4,
        max_attempts: int = 3,
    ) -> None:
        self._users = users
        self._codes = codes
        self._email = email
        self._code_length = code_length
        self._max_attempts = max_attempts

    async def register(self, email: str, password: str) -> None:
        """Create the account and issue an activation code.

        The account is stored with a bcrypt hash (never the plaintext). The
        activation code is persisted in Redis under its TTL before being handed
        to the email sender, so a delivery failure still leaves a usable code.
        The TTL is then refreshed once the email has been sent so the validity
        window starts at delivery and isn't eaten by the email service latency.
        """
        await self._users.create(email, hash_password(password))
        code = generate_code(self._code_length)
        await self._codes.store(email, code)
        await self._email.send_activation_code(email, code)
        await self._codes.refresh(email)

    async def activate(self, email: str, password: str, code: str) -> None:
        """Verify credentials + code (within the TTL) and activate the account.

        Credentials are checked first via :func:`verify_password`, which runs a
        dummy-hash verify for unknown emails so "no such user" and "wrong
        password" are indistinguishable (same 401, same latency).

        A user gets at most ``max_attempts`` (3) guesses against the current
        code; the counter is checked before each guess and incremented on every
        wrong one. Requesting a new code resets the budget.
        """
        email = email.strip().lower()
        user = await self._users.get_by_email(email)
        stored_hash = user.password_hash if user is not None else None
        if not verify_password(password, stored_hash):
            raise InvalidCredentials()

        # verify_password only returns True when the user exists.
        assert user is not None
        if user.is_active:
            return  # activation is idempotent for an already-active account

        # Reject once the attempt budget is exhausted, before touching the code.
        if await self._codes.get_attempts(email) >= self._max_attempts:
            raise TooManyAttempts()

        stored_code = await self._codes.get(email)
        if stored_code is None or not secrets.compare_digest(stored_code, code):
            await self._codes.record_failed_attempt(email)
            raise InvalidOrExpiredCode()

        await self._users.mark_active(user.id)
        await self._codes.delete(email)
