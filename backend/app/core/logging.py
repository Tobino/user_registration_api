"""Structured (JSON) logging with per-request correlation IDs.

The current request's correlation ID lives in a :class:`contextvars.ContextVar`
so any logger -- in routes, services or repositories -- automatically tags its
records with it, without having to thread the ID through every call.
:func:`configure_logging` installs a :class:`JsonFormatter` on the root logger.
"""

from __future__ import annotations

import contextvars
import datetime as dt
import json
import logging

# Set by the correlation-ID middleware for the lifetime of a request; ``None``
# for work outside a request (startup/shutdown, background tasks).
request_id_var: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "request_id", default=None
)


def get_request_id() -> str | None:
    """Return the current request's correlation ID, if any."""
    return request_id_var.get()


class JsonFormatter(logging.Formatter):
    """Render log records as one-line JSON objects.

    Always emits ``timestamp``/``level``/``logger``/``message``; adds
    ``request_id`` when one is bound to the context, an ``exception`` traceback
    when present, and any structured ``extra=`` fields passed to the logger.
    """

    _RESERVED = frozenset(
        logging.makeLogRecord({}).__dict__.keys()
        | {"message", "asctime", "taskName"}
    )

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "timestamp": dt.datetime.fromtimestamp(
                record.created, tz=dt.timezone.utc
            ).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        request_id = request_id_var.get()
        if request_id is not None:
            payload["request_id"] = request_id

        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)

        # Surface any structured fields passed via logger.<level>(..., extra=...).
        for key, value in record.__dict__.items():
            if key not in self._RESERVED and not key.startswith("_"):
                payload[key] = value

        return json.dumps(payload, default=str)


def configure_logging(level: str = "INFO") -> None:
    """Route the root logger through a single JSON-formatted stdout handler.

    Idempotent: replaces any existing handlers, so it is safe to call on every
    startup (and not disturbed by ``logging.basicConfig``).
    """
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())

    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level.upper())
