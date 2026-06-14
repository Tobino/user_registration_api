"""User registration and activation endpoints."""

from fastapi import APIRouter, status

from app.core.security import generate_code
from app.schemas.user import MessageResponse, UserRegistrationRequest

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
async def register_user(payload: UserRegistrationRequest) -> MessageResponse:
    generate_code()
    return MessageResponse(message=_GENERIC_REGISTRATION_MESSAGE)


@router.post(
    "/activate",
    summary="Activate a user account",
)
async def activate_user() -> dict[str, str]:
    """Placeholder activation endpoint."""
    return {"message": "hello world"}
