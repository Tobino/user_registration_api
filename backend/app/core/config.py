"""Centralised application settings.

All configuration is read from environment variables (12-factor style) and
validated by Pydantic. Field names map to upper-case env vars
(``db_host`` -> ``DB_HOST``, ``signup_rate_limit`` -> ``SIGNUP_RATE_LIMIT`` ...).

A single cached :class:`Settings` instance is exposed through
:func:`get_settings`; the app stores it on ``app.state.settings`` at startup and
hands it to consumers through the ``get_settings`` FastAPI dependency, which can
be overridden in tests.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from urllib.parse import quote

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Strongly-typed application configuration."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # --- Observability ------------------------------------------------------
    log_level: str = "INFO"

    # --- PostgreSQL (raw SQL via asyncpg, no ORM) ---------------------------
    # ``database_url`` wins when set (handy for local runs and tests); otherwise
    # the DSN is assembled from the parts below, with the password optionally
    # read from a Docker secret file (``DB_PASSWORD_FILE``).
    database_url: str | None = None
    db_host: str = "db"
    db_port: str = "5432"
    db_user: str = "postgres"
    db_name: str = "users"
    db_password: str = "postgres"
    db_password_file: str | None = None
    db_pool_min_size: int = 1
    db_pool_max_size: int = 10

    # --- Redis (everything that expires) -----------------------------------
    redis_url: str = "redis://redis:6379/0"

    # --- Activation code ----------------------------------------------------
    code_ttl_seconds: int = 60  # the user has one minute to use the code
    # Max number of code guesses allowed per issued activation code.
    activation_max_attempts: int = 3

    # --- Registration rate limit (per client IP) ---------------------------
    signup_rate_limit: int = 50  # at most N registrations per IP...
    signup_rate_limit_window_seconds: int = 3600  # ...within this rolling window

    # --- Third-party email API (mocked by ealen/echo-server in compose) ----
    email_api_url: str = "http://email/"
    email_api_timeout_seconds: float = 5.0
    email_api_retry_attempts: int = 3

    @property
    def resolved_database_url(self) -> str:
        """asyncpg-compatible DSN.

        Returns ``database_url`` verbatim when provided, otherwise assembles the
        DSN from the individual parts -- mirroring the ``POSTGRES_PASSWORD_FILE``
        convention used by the ``db`` service in compose, so the password never
        has to be inlined in the URL.
        """
        if self.database_url:
            return self.database_url

        if self.db_password_file:
            password = Path(self.db_password_file).read_text(encoding="utf-8").strip()
        else:
            password = self.db_password

        return (
            f"postgresql://{self.db_user}:{quote(password, safe='')}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}"
        )


@lru_cache
def get_settings() -> Settings:
    """Return the process-wide cached settings instance."""
    return Settings()
