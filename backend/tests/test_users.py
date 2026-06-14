"""Tests for the user registration and activation endpoints."""

from uuid import uuid4

import bcrypt

from app.repositories.user_repository import UserRecord

_VALID_PAYLOAD = {"email": "user@example.com", "password": "supersecret"}


def _seed_user(user_repository, *, is_active: bool, password: str = "oldpassword"):
    record = UserRecord(
        id=uuid4(),
        email=_VALID_PAYLOAD["email"],
        password_hash=bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode(),
        is_active=is_active,
    )
    user_repository.by_email[record.email] = record
    return record


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


async def test_register_active_account_is_a_noop(
    client, user_repository, code_store, email_sender
):
    # An already-validated account: re-registering must not touch the password
    # nor send a new code, while still returning the generic 202.
    seeded = _seed_user(user_repository, is_active=True)

    resp = await client.post("/users", json=_VALID_PAYLOAD)

    assert resp.status_code == 202
    assert email_sender.sent == []
    assert code_store.codes == {}
    assert user_repository.by_email[seeded.email].password_hash == seeded.password_hash


async def test_register_pending_with_live_code_is_a_noop(
    client, user_repository, code_store, email_sender
):
    # A pending account that still has a valid code in flight: don't resend and
    # don't change the password.
    seeded = _seed_user(user_repository, is_active=False)
    code_store.codes[seeded.email] = "1234"

    resp = await client.post("/users", json=_VALID_PAYLOAD)

    assert resp.status_code == 202
    assert email_sender.sent == []
    assert code_store.codes[seeded.email] == "1234"
    assert user_repository.by_email[seeded.email].password_hash == seeded.password_hash


async def test_register_pending_without_code_updates_password_and_resends(
    client, user_repository, code_store, email_sender
):
    # A pending account whose code has expired: accept the new password and
    # issue a fresh code.
    seeded = _seed_user(user_repository, is_active=False)

    resp = await client.post("/users", json=_VALID_PAYLOAD)

    assert resp.status_code == 202
    assert len(email_sender.sent) == 1
    sent_email, sent_code = email_sender.sent[0]
    assert sent_email == seeded.email
    assert code_store.codes[seeded.email] == sent_code

    new_hash = user_repository.by_email[seeded.email].password_hash
    assert new_hash != seeded.password_hash
    assert bcrypt.checkpw(_VALID_PAYLOAD["password"].encode(), new_hash.encode())


async def test_register_unknown_email_creates_user(client, user_repository):
    assert _VALID_PAYLOAD["email"] not in user_repository.by_email

    resp = await client.post("/users", json=_VALID_PAYLOAD)

    assert resp.status_code == 202
    assert _VALID_PAYLOAD["email"] in user_repository.by_email
    assert user_repository.by_email[_VALID_PAYLOAD["email"]].is_active is False


# Activation endpoint tests live in tests/test_activation.py.
