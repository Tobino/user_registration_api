"""User registration and activation endpoints."""

from fastapi import APIRouter, status

router = APIRouter(prefix="/users", tags=["users"])


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user",
)
async def register_user() -> dict[str, str]:
    """Placeholder registration endpoint."""
    return {"message": "hello world"}


@router.post(
    "/activate",
    summary="Activate a user account",
)
async def activate_user() -> dict[str, str]:
    """Placeholder activation endpoint."""
    return {"message": "hello world"}
