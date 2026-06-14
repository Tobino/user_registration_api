"""Tests for the per-email activation-code send limit (3/hour, 10/day)."""

import fakeredis.aioredis
import pytest

from app.core.exceptions import RateLimitExceeded
from app.services.rate_limit import EmailRateLimiter, RateLimiter

PASSWORD = "s3cretpw!"


@pytest.fixture
def redis_client():
    return fakeredis.aioredis.FakeRedis(decode_responses=True)


# --- EmailRateLimiter unit --------------------------------------------------
async def test_hourly_window_blocks_with_hour_retry_after(redis_client):
    # Daily window left wide so the hourly one is what trips.
    policy = EmailRateLimiter(
        RateLimiter(redis_client), hourly_limit=2, daily_limit=100
    )
    await policy.enforce("a@b.com")
    await policy.enforce("a@b.com")

    with pytest.raises(RateLimitExceeded) as exc_info:
        await policy.enforce("a@b.com")
    assert exc_info.value.retry_after == 3600


async def test_daily_window_blocks_with_day_retry_after(redis_client):
    # Hourly window left wide so the daily one is what trips.
    policy = EmailRateLimiter(
        RateLimiter(redis_client), hourly_limit=100, daily_limit=3
    )
    for _ in range(3):
        await policy.enforce("a@b.com")

    with pytest.raises(RateLimitExceeded) as exc_info:
        await policy.enforce("a@b.com")
    assert exc_info.value.retry_after == 86_400


async def test_budgets_are_per_email(redis_client):
    policy = EmailRateLimiter(
        RateLimiter(redis_client), hourly_limit=1, daily_limit=10
    )
    await policy.enforce("a@b.com")
    with pytest.raises(RateLimitExceeded):
        await policy.enforce("a@b.com")
    # A different address keeps its own budget.
    await policy.enforce("c@d.com")


async def test_blocked_send_does_not_consume_other_window(redis_client):
    # hourly=1 trips on the 2nd send; the daily counter must not have advanced
    # past the one successful send (no phantom record from the blocked call).
    policy = EmailRateLimiter(
        RateLimiter(redis_client), hourly_limit=1, daily_limit=10
    )
    await policy.enforce("a@b.com")
    with pytest.raises(RateLimitExceeded):
        await policy.enforce("a@b.com")
    day_count = await RateLimiter(redis_client).count(
        EmailRateLimiter._day_key("a@b.com"), window_seconds=86_400
    )
    assert day_count == 1


# --- end-to-end through the endpoint ----------------------------------------
async def test_resend_capped_per_hour(client, code_store):
    email = "resend@example.com"
    body = {"email": email, "password": PASSWORD}

    # 3 sends allowed within the hour; delete the code between calls to mimic
    # the 60s code expiring (otherwise a live code short-circuits the resend).
    for _ in range(3):
        resp = await client.post("/users", json=body)
        assert resp.status_code == 202
        await code_store.delete(email)

    # The 4th activation email for this address within the hour is rejected.
    resp = await client.post("/users", json=body)
    assert resp.status_code == 429
    assert resp.headers["Retry-After"] == "3600"
