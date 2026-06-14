"""Shared FastAPI dependencies.

Infrastructure handles (currently just the email sender) live on
``app.state`` and are exposed via ``Depends`` here. Resolving them through
``Depends`` keeps the wiring explicit and lets tests swap any collaborator via
``app.dependency_overrides``.
"""

from __future__ import annotations

from fastapi import Request

from app.services.email import EmailSender


def get_email_sender(request: Request) -> EmailSender:
    return request.app.state.email_sender
