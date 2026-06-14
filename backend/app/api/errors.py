"""Exception handlers translating domain errors into JSON HTTP responses."""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.core.exceptions import DomainError, RateLimitExceeded


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(DomainError)
    async def handle_domain_error(_: Request, exc: DomainError) -> JSONResponse:
        headers: dict[str, str] = {}
        if isinstance(exc, RateLimitExceeded) and exc.retry_after is not None:
            headers["Retry-After"] = str(exc.retry_after)
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.detail},
            headers=headers,
        )
