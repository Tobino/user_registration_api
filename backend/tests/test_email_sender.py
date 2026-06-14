"""Tests for HttpEmailSender: payload, retry, and failure handling.

httpx.MockTransport lets us drive the third-party email API's responses without
any network, so the retry policy is genuinely exercised.
"""

import httpx
import pytest

from app.core.exceptions import EmailDeliveryError
from app.services.email import HttpEmailSender


async def test_sends_payload_with_code():
    captured: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return httpx.Response(200)

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        sender = HttpEmailSender(client, "http://email/", retry_attempts=3)
        await sender.send_activation_code("a@b.com", "1234")

    assert len(captured) == 1
    # The recipient and code travel in the JSON body; the mocked provider
    # (echo-server) logs that body so the code is observable in its logs.
    body = captured[0].content.decode()
    assert "a@b.com" in body
    assert "1234" in body


async def test_retries_transient_errors_then_succeeds():
    attempts = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        attempts["n"] += 1
        if attempts["n"] < 3:
            raise httpx.ConnectError("transient", request=request)
        return httpx.Response(200)

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        sender = HttpEmailSender(client, "http://email/", retry_attempts=3)
        await sender.send_activation_code("a@b.com", "1234")

    assert attempts["n"] == 3


async def test_raises_email_delivery_error_after_exhausting_retries():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500)

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        sender = HttpEmailSender(client, "http://email/", retry_attempts=3)
        with pytest.raises(EmailDeliveryError):
            await sender.send_activation_code("a@b.com", "1234")
