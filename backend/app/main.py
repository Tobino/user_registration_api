"""FastAPI application and lifespan wiring."""

from __future__ import annotations

import logging
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import quote

import httpx
from fastapi import FastAPI

from app.api.errors import register_exception_handlers
from app.api.v1.router import api_router
from app.db.postgres import Database
from app.db.redis import create_redis

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# The third-party email API endpoint. In compose this is the ealen/echo-server
# container, which logs the request body so the 4-digit code is observable via
# `docker compose logs email`.
EMAIL_API_URL = os.environ.get("EMAIL_API_URL", "http://email/")
EMAIL_API_TIMEOUT_SECONDS = float(os.environ.get("EMAIL_API_TIMEOUT_SECONDS", "5.0"))
EMAIL_API_RETRY_ATTEMPTS = int(os.environ.get("EMAIL_API_RETRY_ATTEMPTS", "3"))

# asyncpg-compatible DSN for the PostgreSQL service defined in compose.
DB_POOL_MIN_SIZE = int(os.environ.get("DB_POOL_MIN_SIZE", "1"))
DB_POOL_MAX_SIZE = int(os.environ.get("DB_POOL_MAX_SIZE", "10"))

# Redis holds everything that expires (activation codes, rate-limit counters).
# Defaults to the `redis` service defined in compose.
REDIS_URL = os.environ.get("REDIS_URL", "redis://redis:6379/0")


def _build_database_url() -> str:
    """Resolve the PostgreSQL DSN.

    ``DATABASE_URL`` wins when set (handy for local runs and tests). Otherwise
    the DSN is assembled from individual parts, with the password read from a
    Docker secret file when ``DB_PASSWORD_FILE`` is provided -- mirroring the
    ``POSTGRES_PASSWORD_FILE`` convention used by the ``db`` service in compose,
    so the password never has to be inlined in the URL.
    """
    if url := os.environ.get("DATABASE_URL"):
        return url

    host = os.environ.get("DB_HOST", "db")
    port = os.environ.get("DB_PORT", "5432")
    user = os.environ.get("DB_USER", "postgres")
    name = os.environ.get("DB_NAME", "users")

    if password_file := os.environ.get("DB_PASSWORD_FILE"):
        password = Path(password_file).read_text(encoding="utf-8").strip()
    else:
        password = os.environ.get("DB_PASSWORD", "postgres")

    return f"postgresql://{user}:{quote(password, safe='')}@{host}:{port}/{name}"


DATABASE_URL = _build_database_url()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Open shared connections on startup, close them on shutdown."""
    # Imported here so the module has no hard dependency on the email service
    # at import time (handy for tests that override the dependency).
    from app.services.email import HttpEmailSender

    # Shared PostgreSQL connection pool, opened on startup and closed on
    # shutdown.
    database = Database(
        DATABASE_URL,
        min_size=DB_POOL_MIN_SIZE,
        max_size=DB_POOL_MAX_SIZE,
    )
    await database.connect()
    await database.apply_migrations()

    # Shared Redis client, opened on startup and closed on shutdown.
    redis_client = create_redis(REDIS_URL)

    # One shared HTTP client for the third-party email API, reused across
    # requests (connection pooling) and closed on shutdown.
    http_client = httpx.AsyncClient(timeout=EMAIL_API_TIMEOUT_SECONDS)
    app.state.db = database
    app.state.redis = redis_client
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
        await redis_client.aclose()
        await database.disconnect()
        logger.info("Application shutdown complete")


app = FastAPI(lifespan=lifespan)

register_exception_handlers(app)
app.include_router(api_router)


@app.get("/")
def read_root():
    return {"Hello": "World"}
