"""Pydantic request/response models for the user endpoints."""

from __future__ import annotations

from pydantic import BaseModel, EmailStr, Field, field_validator


class UserRegistrationRequest(BaseModel):
    """Body of ``POST /users``."""

    email: EmailStr
    # bcrypt only considers the first 72 bytes, so we cap there to avoid
    # silently ignoring part of a longer password.
    password: str = Field(min_length=8, max_length=72)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        return value.strip().lower()


class MessageResponse(BaseModel):
    """Generic, enumeration-safe response envelope."""

    message: str
