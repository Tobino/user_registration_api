"""Security helpers."""

from __future__ import annotations

import secrets

import bcrypt

# Cost factor. 12 is a sensible production default (~250ms/verify).
_BCRYPT_ROUNDS = 12


def hash_password(password: str) -> str:
    """Hash a plaintext password with bcrypt and return the encoded string."""
    salt = bcrypt.gensalt(rounds=_BCRYPT_ROUNDS)
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")


def generate_code(length: int = 4) -> str:
    """Return a cryptographically-random zero-padded numeric code."""
    upper_bound = 10**length
    return f"{secrets.randbelow(upper_bound):0{length}d}"
