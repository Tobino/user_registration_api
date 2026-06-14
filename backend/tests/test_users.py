"""Tests for the user registration and activation endpoints."""


async def test_register_user_returns_201(client):
    resp = await client.post("/users")
    assert resp.status_code == 201


async def test_register_user_returns_hello_world(client):
    resp = await client.post("/users")
    assert resp.json() == {"message": "hello world"}


async def test_activate_user_returns_200(client):
    resp = await client.post("/users/activate")
    assert resp.status_code == 200


async def test_activate_user_returns_hello_world(client):
    resp = await client.post("/users/activate")
    assert resp.json() == {"message": "hello world"}
