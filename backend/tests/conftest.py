"""Shared test fixtures.

The suite exercises the real ASGI app in-process via httpx's ASGITransport, with
the third-party email sender replaced by an in-memory fake through
``app.dependency_overrides``. It needs no running server and no external
infrastructure -- just the dev requirements installed.
"""

import httpx
import pytest

from app.api import deps
from app.main import app
from tests.fakes import FakeEmailSender


@pytest.fixture
def email_sender() -> FakeEmailSender:
    return FakeEmailSender()


@pytest.fixture
async def client(email_sender):
    app.dependency_overrides[deps.get_email_sender] = lambda: email_sender
    transport = httpx.ASGITransport(app=app)
    try:
        async with httpx.AsyncClient(
            transport=transport, base_url="http://test"
        ) as ac:
            yield ac
    finally:
        app.dependency_overrides.clear()
