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


def verify_password(password: str, password_hash: str | None) -> bool:
    """Check ``password`` against a stored hash in constant-ish time.

    When ``password_hash`` is ``None`` (no such user) we deliberately perform a
    verify against a dummy hash and return ``False``, so the work done — and
    therefore the latency — matches the "user exists" path. This is the dummy
    hash defence against account enumeration.
    """
    target = password_hash if password_hash is not None else _DUMMY_HASH
    matches = bcrypt.checkpw(password.encode("utf-8"), target.encode("utf-8"))
    # Even if the dummy hash somehow matched, a None hash means "no user".
    return matches and password_hash is not None


def generate_code(length: int = 4) -> str:
    """Return a cryptographically-random zero-padded numeric code."""
    upper_bound = 10**length
    return f"{secrets.randbelow(upper_bound):0{length}d}"


# Computed once at import so every "missing user" verify pays the same cost.
_DUMMY_HASH = hash_password(secrets.token_urlsafe(32))
