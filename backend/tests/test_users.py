"""Tests for the user registration and activation endpoints."""


_VALID_PAYLOAD = {"email": "user@example.com", "password": "supersecret"}


async def test_register_user_returns_202(client):
    resp = await client.post("/users", json=_VALID_PAYLOAD)
    assert resp.status_code == 202


async def test_register_user_returns_generic_message(client):
    resp = await client.post("/users", json=_VALID_PAYLOAD)
    assert resp.json() == {
        "message": "If the email is eligible, an activation code has been sent."
    }


async def test_register_user_sends_4_digit_code_to_email_service(client, email_sender):
    resp = await client.post("/users", json=_VALID_PAYLOAD)
    assert resp.status_code == 202
    assert len(email_sender.sent) == 1
    sent_email, sent_code = email_sender.sent[0]
    assert sent_email == "user@example.com"
    assert len(sent_code) == 4 and sent_code.isdigit()


async def test_register_user_persists_hashed_password(client, user_repository):
    resp = await client.post("/users", json=_VALID_PAYLOAD)
    assert resp.status_code == 202

    record = user_repository.by_email["user@example.com"]
    # The stored hash must not be the plaintext, and must be a bcrypt hash that
    # verifies against the original password.
    assert record.password_hash != _VALID_PAYLOAD["password"]
    assert record.password_hash.startswith("$2")
    import bcrypt

    assert bcrypt.checkpw(
        _VALID_PAYLOAD["password"].encode(), record.password_hash.encode()
    )


async def test_register_user_rejects_invalid_email(client):
    resp = await client.post(
        "/users", json={"email": "not-an-email", "password": "supersecret"}
    )
    assert resp.status_code == 422


async def test_register_user_rejects_short_password(client):
    resp = await client.post(
        "/users", json={"email": "user@example.com", "password": "short"}
    )
    assert resp.status_code == 422


# Activation endpoint tests live in tests/test_activation.py.
