"""Tests for the application's HTTP endpoints."""


async def test_read_root_returns_200(client):
    resp = await client.get("/")
    assert resp.status_code == 200


async def test_read_root_returns_hello_world(client):
    resp = await client.get("/")
    assert resp.json() == {"Hello": "World"}


async def test_read_root_is_json(client):
    resp = await client.get("/")
    assert resp.headers["content-type"].startswith("application/json")


async def test_unknown_path_returns_404(client):
    resp = await client.get("/does-not-exist")
    assert resp.status_code == 404
