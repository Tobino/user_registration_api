"""Tests for the user activation endpoint (Basic auth + 4-digit code).

Activation is gated by HTTP Basic credentials and a 4-digit code, with a cap of
3 invalid code attempts per issued code.
"""

import pytest

EMAIL = "alice@example.com"
PASSWORD = "s3cretpw!"
BODY = {"email": EMAIL, "password": PASSWORD}


async def _register(client):
    await client.post("/users", json=BODY)


async def test_activate_success(client, code_store, user_repository):
    await _register(client)
    code = code_store.codes[EMAIL]

    resp = await client.post(
        "/users/activate", json={"code": code}, auth=(EMAIL, PASSWORD)
    )

    assert resp.status_code == 200
    assert resp.json() == {"message": "Account activated."}
    assert user_repository.by_email[EMAIL].is_active is True
    # The code is single-use: consumed on success.
    assert EMAIL not in code_store.codes


async def test_activate_wrong_password_returns_401(client, code_store, user_repository):
    await _register(client)
    code = code_store.codes[EMAIL]

    resp = await client.post(
        "/users/activate", json={"code": code}, auth=(EMAIL, "wrong-password")
    )

    assert resp.status_code == 401
    assert user_repository.by_email[EMAIL].is_active is False


async def test_activate_unknown_user_returns_401(client):
    resp = await client.post(
        "/users/activate",
        json={"code": "1234"},
        auth=("ghost@example.com", "whatever1"),
    )
    # Same response as wrong-password -> no account enumeration.
    assert resp.status_code == 401


async def test_activate_wrong_code_returns_400(client, code_store, user_repository):
    await _register(client)
    real_code = code_store.codes[EMAIL]
    wrong = "0000" if real_code != "0000" else "1111"

    resp = await client.post(
        "/users/activate", json={"code": wrong}, auth=(EMAIL, PASSWORD)
    )

    assert resp.status_code == 400
    assert user_repository.by_email[EMAIL].is_active is False


async def test_activate_expired_or_missing_code_returns_400(client, code_store):
    await _register(client)
    # Simulate the TTL elapsing: the code is gone from Redis.
    code_store.codes.clear()

    resp = await client.post(
        "/users/activate", json={"code": "1234"}, auth=(EMAIL, PASSWORD)
    )

    assert resp.status_code == 400


async def test_activate_caps_at_three_attempts(client, code_store, user_repository):
    await _register(client)
    real_code = code_store.codes[EMAIL]
    wrong = "0000" if real_code != "0000" else "1111"

    # Three wrong guesses are each answered with 400 (invalid code).
    for _ in range(3):
        resp = await client.post(
            "/users/activate", json={"code": wrong}, auth=(EMAIL, PASSWORD)
        )
        assert resp.status_code == 400

    # The budget is now exhausted: even the *correct* code is rejected with 429.
    resp = await client.post(
        "/users/activate", json={"code": real_code}, auth=(EMAIL, PASSWORD)
    )
    assert resp.status_code == 429
    assert user_repository.by_email[EMAIL].is_active is False


async def test_new_code_resets_attempt_budget(client, code_store):
    await _register(client)
    real_code = code_store.codes[EMAIL]
    wrong = "0000" if real_code != "0000" else "1111"

    for _ in range(3):
        await client.post(
            "/users/activate", json={"code": wrong}, auth=(EMAIL, PASSWORD)
        )

    # Re-registering only issues a new code once the previous one has expired
    # (registration is a no-op while a code is still live). Simulate that expiry
    # so a fresh code — and a fresh budget — can be requested.
    code_store.codes.pop(EMAIL)
    await _register(client)
    fresh_code = code_store.codes[EMAIL]

    resp = await client.post(
        "/users/activate", json={"code": fresh_code}, auth=(EMAIL, PASSWORD)
    )
    assert resp.status_code == 200


async def test_activate_is_idempotent_for_active_account(client, code_store):
    await _register(client)
    code = code_store.codes[EMAIL]
    await client.post("/users/activate", json={"code": code}, auth=(EMAIL, PASSWORD))

    # Second call with any well-formed code still succeeds (already active).
    resp = await client.post(
        "/users/activate", json={"code": "9999"}, auth=(EMAIL, PASSWORD)
    )
    assert resp.status_code == 200


async def test_activate_missing_credentials_returns_401(client, code_store):
    await _register(client)
    code = code_store.codes[EMAIL]
    resp = await client.post("/users/activate", json={"code": code})
    assert resp.status_code == 401


@pytest.mark.parametrize("code", ["123", "12345", "abcd", "12 4", ""])
async def test_activate_malformed_code_returns_422(client, code):
    await _register(client)
    resp = await client.post(
        "/users/activate", json={"code": code}, auth=(EMAIL, PASSWORD)
    )
    assert resp.status_code == 422
