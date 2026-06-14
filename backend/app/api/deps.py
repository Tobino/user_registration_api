"""Shared FastAPI dependencies.

Infrastructure handles (DB pool, email sender) live on ``app.state``.
Repository objects are assembled from them here and exposed via ``Depends``.
Resolving everything through ``Depends`` keeps the wiring explicit and lets
tests swap any collaborator via ``app.dependency_overrides``.
"""

from __future__ import annotations

import os

import redis.asyncio as redis
from fastapi import Depends, Request
from fastapi.security import HTTPBasic

from app.db.postgres import Database
from app.repositories.user_repository import UserRepository
from app.services.codes import CodeStore
from app.services.email import EmailSender
from app.services.user_service import UserService

# Activation codes expire after this validity window (enforced by Redis TTL).
CODE_TTL_SECONDS = int(os.environ.get("CODE_TTL_SECONDS", "60"))

# Maximum number of code guesses allowed per issued activation code.
ACTIVATION_MAX_ATTEMPTS = int(os.environ.get("ACTIVATION_MAX_ATTEMPTS", "3"))

# HTTP Basic auth used by the activation endpoint to identify the user.
basic_auth = HTTPBasic()


def get_email_sender(request: Request) -> EmailSender:
    return request.app.state.email_sender


def get_database(request: Request) -> Database:
    return request.app.state.db


def get_redis(request: Request) -> redis.Redis:
    return request.app.state.redis


def get_user_repository(db: Database = Depends(get_database)) -> UserRepository:
    return UserRepository(db.pool)


def get_code_store(client: redis.Redis = Depends(get_redis)) -> CodeStore:
    return CodeStore(client, CODE_TTL_SECONDS)


def get_user_service(
    users: UserRepository = Depends(get_user_repository),
    codes: CodeStore = Depends(get_code_store),
    email: EmailSender = Depends(get_email_sender),
) -> UserService:
    return UserService(users, codes, email, max_attempts=ACTIVATION_MAX_ATTEMPTS)
