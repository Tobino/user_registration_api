"""Shared FastAPI dependencies.

Infrastructure handles (DB pool, email sender) live on ``app.state``.
Repository objects are assembled from them here and exposed via ``Depends``.
Resolving everything through ``Depends`` keeps the wiring explicit and lets
tests swap any collaborator via ``app.dependency_overrides``.
"""

from __future__ import annotations

from fastapi import Depends, Request

from app.db.postgres import Database
from app.repositories.user_repository import UserRepository
from app.services.email import EmailSender


def get_email_sender(request: Request) -> EmailSender:
    return request.app.state.email_sender


def get_database(request: Request) -> Database:
    return request.app.state.db


def get_user_repository(db: Database = Depends(get_database)) -> UserRepository:
    return UserRepository(db.pool)
