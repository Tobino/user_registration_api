"""Domain-level exceptions.

These are raised by the service layer and translated into HTTP responses by the
handlers registered in :mod:`app.api.errors`. Keeping them free of FastAPI types
means the business logic stays framework-agnostic and unit-testable.
"""

from __future__ import annotations


class DomainError(Exception):
    """Base class for all expected, client-facing errors.

    ``status_code`` and ``detail`` give the error handler everything it needs to
    build a uniform JSON response.
    """

    status_code: int = 400
    detail: str = "Request could not be processed."

    def __init__(self, detail: str | None = None) -> None:
        if detail is not None:
            self.detail = detail
        super().__init__(self.detail)


class EmailDeliveryError(DomainError):
    """The third-party email API could not be reached after retries."""

    status_code = 502
    detail = "Could not send the activation email. Please try again later."
