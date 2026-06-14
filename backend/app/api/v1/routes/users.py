"""User registration and activation endpoints."""

from fastapi import APIRouter, Depends, status

from app.api.deps import get_email_sender
from app.core.security import generate_code
from app.schemas.user import MessageResponse, UserRegistrationRequest
from app.services.email import EmailSender

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
    email_sender: EmailSender = Depends(get_email_sender),
) -> MessageResponse:
    # Persistence and rate limiting are still out of scope: we only generate the
    # 4-digit code and hand it to the third-party email service (which, in
    # compose, logs it so it can be observed).
    code = generate_code()
    await email_sender.send_activation_code(payload.email, code)
    return MessageResponse(message=_GENERIC_REGISTRATION_MESSAGE)


@router.post(
    "/activate",
    summary="Activate a user account",
)
async def activate_user() -> dict[str, str]:
    """Placeholder activation endpoint."""
    return {"message": "hello world"}
