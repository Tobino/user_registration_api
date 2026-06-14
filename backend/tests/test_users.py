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


async def test_activate_user_returns_200(client):
    resp = await client.post("/users/activate")
    assert resp.status_code == 200


async def test_activate_user_returns_hello_world(client):
    resp = await client.post("/users/activate")
    assert resp.json() == {"message": "hello world"}
