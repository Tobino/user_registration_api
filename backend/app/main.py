"""FastAPI application and lifespan wiring."""

from __future__ import annotations

import logging
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI

from app.api.errors import register_exception_handlers
from app.api.v1.router import api_router

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# The third-party email API endpoint. In compose this is the ealen/echo-server
# container, which logs the request body so the 4-digit code is observable via
# `docker compose logs email`.
EMAIL_API_URL = os.environ.get("EMAIL_API_URL", "http://email/")
EMAIL_API_TIMEOUT_SECONDS = float(os.environ.get("EMAIL_API_TIMEOUT_SECONDS", "5.0"))
EMAIL_API_RETRY_ATTEMPTS = int(os.environ.get("EMAIL_API_RETRY_ATTEMPTS", "3"))


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Open shared connections on startup, close them on shutdown."""
    # Imported here so the module has no hard dependency on the email service
    # at import time (handy for tests that override the dependency).
    from app.services.email import HttpEmailSender

    # One shared HTTP client for the third-party email API, reused across
    # requests (connection pooling) and closed on shutdown.
    http_client = httpx.AsyncClient(timeout=EMAIL_API_TIMEOUT_SECONDS)
    app.state.email_sender = HttpEmailSender(
        http_client,
        EMAIL_API_URL,
        retry_attempts=EMAIL_API_RETRY_ATTEMPTS,
    )
    logger.info("Application startup complete")

    try:
        yield
    finally:
        await http_client.aclose()
        logger.info("Application shutdown complete")


app = FastAPI(lifespan=lifespan)

register_exception_handlers(app)
app.include_router(api_router)


@app.get("/")
def read_root():
    return {"Hello": "World"}
