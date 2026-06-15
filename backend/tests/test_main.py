"""Tests for the application's HTTP endpoints."""


async def test_unknown_path_returns_404(client):
    resp = await client.get("/does-not-exist")
    assert resp.status_code == 404
