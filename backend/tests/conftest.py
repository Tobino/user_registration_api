"""Shared test fixtures.

The suite exercises the real ASGI app in-process via httpx's ASGITransport, with
the third-party email sender replaced by an in-memory fake through
``app.dependency_overrides``. It needs no running server and no external
infrastructure -- just the dev requirements installed.
"""

import fakeredis.aioredis
import httpx
import pytest

from app.api import deps
from app.core.config import Settings
from app.main import app
from app.services.rate_limit import RateLimiter, RegistrationRateLimiter
from tests.fakes import FakeCodeStore, FakeEmailSender, FakeUserRepository

# Fixed client IP injected into the ASGI scope so per-IP rate-limit tests are
# deterministic (every request shares the same signup-ip bucket).
TEST_CLIENT_IP = "203.0.113.7"


@pytest.fixture
def email_sender() -> FakeEmailSender:
    return FakeEmailSender()


@pytest.fixture
def user_repository() -> FakeUserRepository:
    return FakeUserRepository()


@pytest.fixture
def code_store() -> FakeCodeStore:
    return FakeCodeStore()


@pytest.fixture
def settings() -> Settings:
    return Settings()


@pytest.fixture
def fake_redis() -> fakeredis.aioredis.FakeRedis:
    return fakeredis.aioredis.FakeRedis(decode_responses=True)


@pytest.fixture
def rate_limiter(fake_redis, settings) -> RegistrationRateLimiter:
    # Real sliding-window limiter backed by fakeredis, so the throttling logic
    # is genuinely exercised. Uses the same defaults as production wiring.
    return RegistrationRateLimiter(
        RateLimiter(fake_redis),
        limit=settings.signup_rate_limit,
        window_seconds=settings.signup_rate_limit_window_seconds,
    )


@pytest.fixture
async def client(email_sender, user_repository, code_store, rate_limiter):
    app.dependency_overrides[deps.get_email_sender] = lambda: email_sender
    app.dependency_overrides[deps.get_user_repository] = lambda: user_repository
    app.dependency_overrides[deps.get_code_store] = lambda: code_store
    app.dependency_overrides[deps.get_registration_rate_limiter] = lambda: rate_limiter
    transport = httpx.ASGITransport(app=app, client=(TEST_CLIENT_IP, 12345))
    try:
        async with httpx.AsyncClient(
            transport=transport, base_url="http://test"
        ) as ac:
            yield ac
    finally:
        app.dependency_overrides.clear()
