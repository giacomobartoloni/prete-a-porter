"""Environment access for the Chainlit service: persistence and auth switches.

Everything the chat core needs (LLM keys, A2A URLs, timeouts, quota limits) is
read by the core from the same environment. This module owns the settings that
belong to this service, plus the validation that makes a misconfigured
deployment fail at startup instead of at the first login.
"""

import os

DATABASE_URL_ENV = "DATABASE_URL"
AUTH_SECRET_ENV = "CHAINLIT_AUTH_SECRET"


class ConfigurationError(RuntimeError):
    """The service cannot run with this environment."""


def database_url() -> str | None:
    """PostgreSQL URL for Chainlit's SQLAlchemy data layer, or ``None``.

    Persistence is opt-in and explicit: only a ``postgresql+asyncpg://`` URL
    enables it. The repository ``.env`` also carries the legacy frontend's
    Prisma URL (``file:…``); treating anything else as "persistence off" keeps
    the rollback switch — run without a database — a single env override
    instead of an asyncpg crash at the first login.
    """
    raw = (os.environ.get(DATABASE_URL_ENV) or "").strip()
    return raw if raw.startswith("postgresql+asyncpg://") else None


def persistence_enabled() -> bool:
    """True when a data layer (and therefore authentication) is configured."""
    return database_url() is not None


def auth_secret() -> str | None:
    """Session-signing secret; Chainlit asserts on it at login time."""
    return (os.environ.get(AUTH_SECRET_ENV) or "").strip() or None


def validate() -> None:
    """Fail loudly on a configuration that cannot work at runtime.

    Raises:
        ConfigurationError: persistence is enabled but no session secret is
            present, so every login would crash with an AssertionError inside
            Chainlit's JWT module.
    """
    if persistence_enabled() and auth_secret() is None:
        raise ConfigurationError(
            f"{AUTH_SECRET_ENV} is required when {DATABASE_URL_ENV} enables persistence and "
            "authentication. Generate one with `openssl rand -hex 32`."
        )
