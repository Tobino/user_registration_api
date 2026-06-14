"""Third-party email API client.

The SMTP/email provider is treated as an external HTTP service. The concrete
:class:`HttpEmailSender` POSTs a JSON payload to a configured endpoint using
``httpx.AsyncClient`` and retries transient failures with tenacity. In compose
that endpoint is an ealen/echo-server container, which logs the request body, so
the 4-digit code shows up in its logs (`docker compose logs email`); in
production it would be a real provider (SendGrid, Mailgun, …).

The :class:`EmailSender` Protocol lets callers depend on the behaviour, not the
implementation, so tests inject a fake.
"""

from __future__ import annotations

import logging
from typing import Protocol

import httpx
from tenacity import (
    AsyncRetrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.core.exceptions import EmailDeliveryError

logger = logging.getLogger(__name__)


class EmailSender(Protocol):
    async def send_activation_code(self, email: str, code: str) -> None: ...


class HttpEmailSender:
    def __init__(
        self,
        client: httpx.AsyncClient,
        url: str,
        *,
        retry_attempts: int = 3,
    ) -> None:
        self._client = client
        self._url = url
        self._retry_attempts = retry_attempts

    async def send_activation_code(self, email: str, code: str) -> None:
        payload = {
            "to": email,
            "subject": "Your activation code",
            "body": f"Your activation code is {code}. It expires in 60 seconds.",
        }
        try:
            async for attempt in AsyncRetrying(
                stop=stop_after_attempt(self._retry_attempts),
                wait=wait_exponential(multiplier=0.2, max=2),
                retry=retry_if_exception_type(httpx.HTTPError),
                reraise=True,
            ):
                with attempt:
                    response = await self._client.post(self._url, json=payload)
                    response.raise_for_status()
        except httpx.HTTPError as exc:
            logger.error("Email delivery failed after retries: %s", exc)
            raise EmailDeliveryError() from exc
