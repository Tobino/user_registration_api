"""Shared test fixtures.

The suite exercises the real ASGI app in-process via httpx's ASGITransport, so
it needs no running server and no external infrastructure -- just the dev
requirements installed.
"""

import httpx
import pytest

from app.main import app


@pytest.fixture
async def client():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://test"
    ) as ac:
        yield ac
