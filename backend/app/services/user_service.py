"""User registration/activation business logic.

It orchestrates the repository, the Redis-backed code store, and the email
sender, and raises :class:`~app.core.exceptions.DomainError` subclasses that the
API turns into HTTP responses.
"""

from __future__ import annotations

import logging
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

logger = logging.getLogger(__name__)


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
        """Create or re-prime a pending account and issue an activation code.

        The endpoint is enumeration-safe: every caller gets the same generic
        response, and the bcrypt hash is computed on every branch so the timing
        doesn't reveal whether the email already exists.

        Branches, in order:

        * **unknown email** — create the account and send a code;
        * **already active** — do nothing, the account is registered;
        * **pending with a live code** — do nothing, a code is already in
          flight (avoids resending while one is still valid);
        * **pending with no live code** — update the password and send a fresh
          code, letting the user pick up where an expired code left off.
        """
        # Hash on every path (even the do-nothing ones) so the dominant cost is
        # identical regardless of branch — the timing must not leak existence.
        # NB: never log the plaintext password or the activation code.
        logger.info("register: start email=%s", email)
        password_hash = hash_password(password)

        existing = await self._users.get_by_email(email)
        if existing is None:
            logger.info("register: unknown email=%s -> creating account", email)
            await self._users.create(email, password_hash)
        elif existing.is_active:
            logger.info(
                "register: email=%s already active -> no-op (id=%s)",
                email,
                existing.id,
            )
            return
        elif await self._codes.get(email) is not None:
            logger.info(
                "register: email=%s pending with a live code -> no-op, not resending"
                " (id=%s)",
                email,
                existing.id,
            )
            return
        else:
            logger.info(
                "register: email=%s pending without a code -> updating password"
                " (id=%s)",
                email,
                existing.id,
            )
            await self._users.update_password(existing.id, password_hash)

        await self._issue_code(email)

    async def _issue_code(self, email: str) -> None:
        """Generate, store, and email a fresh activation code.

        The code is persisted in Redis under its TTL before being handed to the
        email sender, so a delivery failure still leaves a usable code. The TTL
        is refreshed once the email has been sent so the validity window starts
        at delivery and isn't eaten by the email service latency.
        """
        code = generate_code(self._code_length)
        await self._codes.store(email, code)
        logger.info("issue_code: code stored in Redis for email=%s", email)
        await self._email.send_activation_code(email, code)
        await self._codes.refresh(email)
        logger.info("issue_code: code sent and TTL refreshed for email=%s", email)

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
        logger.info("activate: start email=%s", email)
        user = await self._users.get_by_email(email)
        stored_hash = user.password_hash if user is not None else None
        if not verify_password(password, stored_hash):
            logger.warning(
                "activate: invalid credentials email=%s (user_exists=%s)",
                email,
                user is not None,
            )
            raise InvalidCredentials()

        # verify_password only returns True when the user exists.
        assert user is not None
        if user.is_active:
            logger.info("activate: email=%s already active -> no-op (id=%s)", email, user.id)
            return  # activation is idempotent for an already-active account

        # Reject once the attempt budget is exhausted, before touching the code.
        attempts = await self._codes.get_attempts(email)
        if attempts >= self._max_attempts:
            logger.warning(
                "activate: too many attempts email=%s (%d/%d)",
                email,
                attempts,
                self._max_attempts,
            )
            raise TooManyAttempts()

        stored_code = await self._codes.get(email)
        if stored_code is None or not secrets.compare_digest(stored_code, code):
            count = await self._codes.record_failed_attempt(email)
            logger.warning(
                "activate: invalid/expired code email=%s (expired=%s, attempt=%d/%d)",
                email,
                stored_code is None,
                count,
                self._max_attempts,
            )
            raise InvalidOrExpiredCode()

        await self._users.mark_active(user.id)
        await self._codes.delete(email)
        logger.info("activate: success email=%s account activated (id=%s)", email, user.id)
