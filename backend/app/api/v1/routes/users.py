"""User registration and activation endpoints."""

from fastapi import APIRouter, Depends, Request, status
from fastapi.security import HTTPBasicCredentials

from app.api.deps import (
    basic_auth,
    get_registration_rate_limiter,
    get_user_service,
)
from app.schemas.user import (
    ActivationRequest,
    ErrorResponse,
    MessageResponse,
    UserRegistrationRequest,
)
from app.services.rate_limit import RegistrationRateLimiter
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
    description=(
        "Register a user and email a 4-digit activation code. The response is "
        "always the same generic `202` regardless of whether the email is new, "
        "pending, or already active, so the endpoint never reveals which "
        "accounts exist. Throttled per client IP (default 50 / hour)."
    ),
    responses={
        202: {
            "description": "Request accepted; an activation code is sent if eligible",
            "content": {
                "application/json": {
                    "example": {
                        "message": (
                            "If the email is eligible, an activation code has "
                            "been sent."
                        )
                    }
                }
            },
        },
        422: {"description": "Payload validation error (e.g. invalid email or short password)"},
        429: {
            "description": "Per-IP registration rate limit exceeded (sets `Retry-After`)",
            "model": ErrorResponse,
            "content": {
                "application/json": {
                    "example": {"detail": "Too many requests. Please try again later."}
                }
            },
        },
    },
)
async def register_user(
    payload: UserRegistrationRequest,
    request: Request,
    service: UserService = Depends(get_user_service),
    rate_limiter: RegistrationRateLimiter = Depends(get_registration_rate_limiter),
) -> MessageResponse:
    # Throttle account creation per client IP (default 50/hour) before doing any
    # work, raising 429 once the budget is spent. request.client.host reflects
    # the real client IP because uvicorn runs with --proxy-headers behind nginx
    # (which forwards X-Forwarded-For).
    client_ip = request.client.host if request.client else "unknown"
    await rate_limiter.enforce(client_ip)

    # The service persists the account (bcrypt hash, never the plaintext),
    # stores the activation code in Redis under its TTL, and hands it to the
    # third-party email service. Duplicate registrations are silently ignored
    # by the repository (ON CONFLICT DO NOTHING) so the response stays
    # enumeration-safe.
    await service.register(payload.email, payload.password)
    return MessageResponse(message=_GENERIC_REGISTRATION_MESSAGE)


@router.post(
    "/activate",
    response_model=MessageResponse,
    summary="Activate a user account with the 4-digit code",
    description=(
        "Activate a pending account. The user is identified through HTTP Basic "
        "auth (email + password); only the 4-digit code travels in the body. "
        "The code is valid for 60 seconds and allows at most 3 attempts before "
        "a fresh code must be requested."
    ),
    responses={
        200: {
            "description": "Account activated",
            "content": {
                "application/json": {"example": {"message": "Account activated."}}
            },
        },
        400: {
            "description": "Invalid, already-used, or expired activation code",
            "model": ErrorResponse,
            "content": {
                "application/json": {
                    "example": {"detail": "Invalid or expired activation code."}
                }
            },
        },
        401: {
            "description": "Invalid Basic auth credentials",
            "model": ErrorResponse,
            "content": {
                "application/json": {"example": {"detail": "Invalid credentials."}}
            },
        },
        422: {"description": "Payload validation error (code must be 4 digits)"},
        429: {
            "description": "The 3-attempt cap on this code has been exhausted",
            "model": ErrorResponse,
            "content": {
                "application/json": {
                    "example": {
                        "detail": (
                            "Too many invalid activation attempts. Request a new "
                            "code."
                        )
                    }
                }
            },
        },
    },
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
