"""In-memory test doubles for the service collaborators."""

from __future__ import annotations


class FakeEmailSender:
    """Records every activation code it is asked to send instead of doing HTTP."""

    def __init__(self) -> None:
        self.sent: list[tuple[str, str]] = []

    async def send_activation_code(self, email: str, code: str) -> None:
        self.sent.append((email, code))
