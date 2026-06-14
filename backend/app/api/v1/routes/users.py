"""User registration and activation endpoints."""

from fastapi import APIRouter, Depends, status
from fastapi.security import HTTPBasicCredentials

from app.api.deps import basic_auth, get_user_service
from app.schemas.user import (
    ActivationRequest,
    MessageResponse,
    UserRegistrationRequest,
)
from app.services.user_service import UserService

router = APIRouter(prefix="/users", tags=["users"])

# Identical response on every outcome (new / pending / already-active) so the
# endpoint never reveals whether an email is registered.
_GENERIC_REGISTRATION_MESSAGE = (
    "If the email is eligible, an activation code has been sent."
)


@router.post(
    "",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=MessageResponse,
    summary="Register a new user and send an activation code",
)
async def register_user(
    payload: UserRegistrationRequest,
    service: UserService = Depends(get_user_service),
) -> MessageResponse:
    # The service persists the account (bcrypt hash, never the plaintext),
    # stores the activation code in Redis under its TTL, and hands it to the
    # third-party email service. Duplicate registrations are silently ignored
    # by the repository (ON CONFLICT DO NOTHING) so the response stays
    # enumeration-safe. Rate limiting is still out of scope.
    await service.register(payload.email, payload.password)
    return MessageResponse(message=_GENERIC_REGISTRATION_MESSAGE)


@router.post(
    "/activate",
    response_model=MessageResponse,
    summary="Activate a user account with the 4-digit code",
)
async def activate_user(
    payload: ActivationRequest,
    credentials: HTTPBasicCredentials = Depends(basic_auth),
    service: UserService = Depends(get_user_service),
) -> MessageResponse:
    # The account is identified via HTTP Basic auth; only the code is in the
    # body. A user gets at most 3 guesses per issued code before being locked
    # out until a new code is requested.
    await service.activate(credentials.username, credentials.password, payload.code)
    return MessageResponse(message="Account activated.")
