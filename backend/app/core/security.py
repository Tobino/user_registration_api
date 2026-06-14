"""Security helpers."""

from __future__ import annotations

import secrets


def generate_code(length: int = 4) -> str:
    """Return a cryptographically-random zero-padded numeric code."""
    upper_bound = 10**length
    return f"{secrets.randbelow(upper_bound):0{length}d}"
