"""User registration business logic.

It orchestrates the repository, the Redis-backed code store, and the email sender.
"""

from __future__ import annotations

from app.core.security import generate_code, hash_password
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
    ) -> None:
        self._users = users
        self._codes = codes
        self._email = email
        self._code_length = code_length

    async def register(self, email: str, password: str) -> None:
        """Create the account and issue an activation code.

        The account is stored with a bcrypt hash (never the plaintext). The
        activation code is persisted in Redis under its TTL before being handed
        to the email sender, so a delivery failure still leaves a usable code.
        """
        await self._users.create(email, hash_password(password))
        code = generate_code(self._code_length)
        await self._codes.store(email, code)
        await self._email.send_activation_code(email, code)
