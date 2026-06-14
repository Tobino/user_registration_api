"""Unit tests for the Redis-backed CodeStore (run against fakeredis)."""

import fakeredis.aioredis
import pytest

from app.services.codes import CodeStore


@pytest.fixture
def redis_client():
    return fakeredis.aioredis.FakeRedis(decode_responses=True)


async def test_store_get_delete_roundtrip(redis_client):
    store = CodeStore(redis_client, ttl_seconds=60)
    await store.store("a@b.com", "1234")

    assert await store.get("a@b.com") == "1234"
    await store.delete("a@b.com")
    assert await store.get("a@b.com") is None


async def test_store_sets_ttl(redis_client):
    store = CodeStore(redis_client, ttl_seconds=60)
    await store.store("a@b.com", "1234")
    ttl = await redis_client.ttl("activation:code:a@b.com")
    assert 0 < ttl <= 60


async def test_get_missing_returns_none(redis_client):
    store = CodeStore(redis_client, ttl_seconds=60)
    assert await store.get("nobody@b.com") is None
