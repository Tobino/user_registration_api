"""Redis client factory.

Redis holds everything that is meant to expire: activation codes, failed-attempt
sliding windows, and rate-limit counters. ``decode_responses`` is enabled so the
rest of the code works with ``str`` rather than ``bytes``.
"""

from __future__ import annotations

import redis.asyncio as redis


def create_redis(url: str) -> redis.Redis:
    return redis.from_url(url, decode_responses=True)
