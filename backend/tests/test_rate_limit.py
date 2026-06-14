"""Tests for the per-IP registration rate limit.

The generic sliding-window :class:`RateLimiter` and the
:class:`RegistrationRateLimiter` policy are unit-tested against fakeredis; the
``POST /users`` throttle (default 50/hour/IP) is exercised end-to-end through
the ASGI app.
"""

import fakeredis.aioredis
import pytest

from app.core.exceptions import RateLimitExceeded
from app.services.rate_limit import RateLimiter, RegistrationRateLimiter

PASSWORD = "s3cretpw!"


@pytest.fixture
def redis_client():
    return fakeredis.aioredis.FakeRedis(decode_responses=True)


# --- generic RateLimiter ----------------------------------------------------
async def test_allow_until_limit_then_blocks(redis_client):
    limiter = RateLimiter(redis_client)
    assert await limiter.allow("k", limit=2, window_seconds=60) is True
    assert await limiter.allow("k", limit=2, window_seconds=60) is True
    assert await limiter.allow("k", limit=2, window_seconds=60) is False


async def test_count_reflects_records(redis_client):
    limiter = RateLimiter(redis_client)
    assert await limiter.count("k", window_seconds=60) == 0
    await limiter.record("k", window_seconds=60)
    await limiter.record("k", window_seconds=60)
    assert await limiter.count("k", window_seconds=60) == 2


async def test_entries_outside_window_are_pruned(redis_client):
    limiter = RateLimiter(redis_client)
    # An entry scored at epoch 0 is far older than any recent window.
    await redis_client.zadd("k", {"stale": 0})
    assert await limiter.count("k", window_seconds=60) == 0


async def test_record_sets_expiry(redis_client):
    limiter = RateLimiter(redis_client)
    await limiter.record("k", window_seconds=120)
    ttl = await redis_client.ttl("k")
    assert 0 < ttl <= 120


# --- RegistrationRateLimiter policy -----------------------------------------
async def test_enforce_allows_up_to_limit_then_raises(redis_client):
    policy = RegistrationRateLimiter(
        RateLimiter(redis_client), limit=3, window_seconds=3600
    )
    for _ in range(3):
        await policy.enforce("1.2.3.4")  # within budget -> no raise

    with pytest.raises(RateLimitExceeded) as exc_info:
        await policy.enforce("1.2.3.4")
    assert exc_info.value.retry_after == 3600


async def test_enforce_is_per_ip(redis_client):
    policy = RegistrationRateLimiter(
        RateLimiter(redis_client), limit=1, window_seconds=3600
    )
    await policy.enforce("1.1.1.1")
    with pytest.raises(RateLimitExceeded):
        await policy.enforce("1.1.1.1")
    # A different IP keeps its own independent budget.
    await policy.enforce("2.2.2.2")


# --- end-to-end through the endpoint ----------------------------------------
async def test_registration_capped_per_ip(client):
    # The first 50 registrations from the same client IP succeed.
    for i in range(50):
        resp = await client.post(
            "/users", json={"email": f"user{i}@example.com", "password": PASSWORD}
        )
        assert resp.status_code == 202

    # The 51st within the rolling hour is rejected with 429 + Retry-After.
    resp = await client.post(
        "/users", json={"email": "overflow@example.com", "password": PASSWORD}
    )
    assert resp.status_code == 429
    assert resp.headers["Retry-After"] == "3600"
