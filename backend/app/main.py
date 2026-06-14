"""FastAPI application and lifespan wiring."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI

from app.api.errors import register_exception_handlers
from app.api.v1.router import api_router
from app.core.config import Settings, get_settings
from app.db.postgres import Database
from app.db.redis import create_redis

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Open shared connections on startup, close them on shutdown."""
    # Imported here so the module has no hard dependency on the email service
    # at import time (handy for tests that override the dependency).
    from app.services.email import HttpEmailSender

    settings: Settings = app.state.settings

    # Shared PostgreSQL connection pool, opened on startup and closed on
    # shutdown.
    database = Database(
        settings.resolved_database_url,
        min_size=settings.db_pool_min_size,
        max_size=settings.db_pool_max_size,
    )
    await database.connect()
    await database.apply_migrations()

    # Shared Redis client, opened on startup and closed on shutdown.
    redis_client = create_redis(settings.redis_url)

    # One shared HTTP client for the third-party email API, reused across
    # requests (connection pooling) and closed on shutdown.
    http_client = httpx.AsyncClient(timeout=settings.email_api_timeout_seconds)
    app.state.db = database
    app.state.redis = redis_client
    app.state.email_sender = HttpEmailSender(
        http_client,
        settings.email_api_url,
        retry_attempts=settings.email_api_retry_attempts,
    )
    logger.info("Application startup complete")

    try:
        yield
    finally:
        await http_client.aclose()
        await redis_client.aclose()
        await database.disconnect()
        logger.info("Application shutdown complete")


app = FastAPI(lifespan=lifespan)
# Settings are resolved once and stashed on app.state at construction time (not
# in the lifespan), so dependencies can read them even when the lifespan isn't
# run -- e.g. under httpx's ASGITransport in the test suite.
app.state.settings = get_settings()

register_exception_handlers(app)
app.include_router(api_router)


@app.get("/")
def read_root():
    return {"Hello": "World"}
