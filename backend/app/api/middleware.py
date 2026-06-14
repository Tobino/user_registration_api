"""ASGI middleware binding a correlation ID to every request.

Implemented as a *pure ASGI* middleware (not ``BaseHTTPMiddleware``) so the
``ContextVar`` set here is visible to the endpoint and the services it calls --
``BaseHTTPMiddleware`` runs the downstream app in a separate task, which would
break that propagation.
"""

from __future__ import annotations

from uuid import uuid4

from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.core.logging import request_id_var

_HEADER_NAME = b"x-request-id"


class CorrelationIdMiddleware:
    """Reuse an inbound ``X-Request-ID`` or mint one, and echo it on the way out."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        incoming = dict(scope["headers"]).get(_HEADER_NAME)
        request_id = incoming.decode("latin-1") if incoming else uuid4().hex
        token = request_id_var.set(request_id)

        async def send_with_request_id(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = message.setdefault("headers", [])
                headers.append((_HEADER_NAME, request_id.encode("latin-1")))
            await send(message)

        try:
            await self.app(scope, receive, send_with_request_id)
        finally:
            request_id_var.reset(token)
