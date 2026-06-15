"""Tests for JSON logging and request correlation IDs."""

import json
import logging

from app.core.logging import JsonFormatter, request_id_var


def _record(**kwargs) -> logging.LogRecord:
    defaults = dict(
        name="app.test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="hello %s",
        args=("world",),
        exc_info=None,
    )
    defaults.update(kwargs)
    return logging.LogRecord(**defaults)


def test_formatter_emits_valid_json_with_core_fields():
    payload = json.loads(JsonFormatter().format(_record()))
    assert payload["level"] == "INFO"
    assert payload["logger"] == "app.test"
    assert payload["message"] == "hello world"
    assert "timestamp" in payload
    assert "request_id" not in payload  # none bound -> omitted


def test_formatter_includes_request_id_when_bound():
    token = request_id_var.set("abc123")
    try:
        payload = json.loads(JsonFormatter().format(_record()))
    finally:
        request_id_var.reset(token)
    assert payload["request_id"] == "abc123"


def test_formatter_surfaces_extra_fields():
    record = _record()
    record.email = "user@example.com"  # mimics logger.info(..., extra={...})
    payload = json.loads(JsonFormatter().format(record))
    assert payload["email"] == "user@example.com"


def test_formatter_includes_exception():
    try:
        raise ValueError("boom")
    except ValueError:
        import sys

        payload = json.loads(JsonFormatter().format(_record(exc_info=sys.exc_info())))
    assert "ValueError: boom" in payload["exception"]


async def test_response_carries_generated_request_id(client):
    resp = await client.get("/openapi.json")
    assert resp.status_code == 200
    assert resp.headers.get("X-Request-ID")  # a fresh id was minted


async def test_inbound_request_id_is_echoed(client):
    resp = await client.get("/openapi.json", headers={"X-Request-ID": "trace-42"})
    assert resp.headers["X-Request-ID"] == "trace-42"
