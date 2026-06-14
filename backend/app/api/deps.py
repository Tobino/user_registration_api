"""Shared FastAPI dependencies.

Infrastructure handles (settings, DB pool, Redis client, email sender) live on
``app.state``. Repository/service objects are assembled from them here and
exposed via ``Depends``. Resolving everything through ``Depends`` keeps the
wiring explicit and lets tests swap any collaborator via
``app.dependency_overrides``.
"""

from __future__ import annotations

import redis.asyncio as redis
from fastapi import Depends, Request
from fastapi.security import HTTPBasic

from app.core.config import Settings
from app.db.postgres import Database
from app.repositories.user_repository import UserRepository
from app.services.codes import CodeStore
from app.services.email import EmailSender
from app.services.rate_limit import (
    EmailRateLimiter,
    RateLimiter,
    RegistrationRateLimiter,
)
from app.services.user_service import UserService

# HTTP Basic auth used by the activation endpoint to identify the user.
basic_auth = HTTPBasic()


# --- infrastructure ---------------------------------------------------------
def get_settings(request: Request) -> Settings:
    return request.app.state.settings


def get_email_sender(request: Request) -> EmailSender:
    return request.app.state.email_sender


def get_database(request: Request) -> Database:
    return request.app.state.db


def get_redis(request: Request) -> redis.Redis:
    return request.app.state.redis


# --- repositories / services ------------------------------------------------
def get_user_repository(db: Database = Depends(get_database)) -> UserRepository:
    return UserRepository(db.pool)


def get_code_store(
    client: redis.Redis = Depends(get_redis),
    settings: Settings = Depends(get_settings),
) -> CodeStore:
    return CodeStore(client, settings.code_ttl_seconds)


def get_registration_rate_limiter(
    client: redis.Redis = Depends(get_redis),
    settings: Settings = Depends(get_settings),
) -> RegistrationRateLimiter:
    return RegistrationRateLimiter(
        RateLimiter(client),
        limit=settings.signup_rate_limit,
        window_seconds=settings.signup_rate_limit_window_seconds,
    )


def get_email_rate_limiter(
    client: redis.Redis = Depends(get_redis),
    settings: Settings = Depends(get_settings),
) -> EmailRateLimiter:
    return EmailRateLimiter(
        RateLimiter(client),
        hourly_limit=settings.email_send_hourly_limit,
        daily_limit=settings.email_send_daily_limit,
    )


def get_user_service(
    users: UserRepository = Depends(get_user_repository),
    codes: CodeStore = Depends(get_code_store),
    email: EmailSender = Depends(get_email_sender),
    email_limiter: EmailRateLimiter = Depends(get_email_rate_limiter),
    settings: Settings = Depends(get_settings),
) -> UserService:
    return UserService(
        users,
        codes,
        email,
        email_limiter,
        max_attempts=settings.activation_max_attempts,
    )
