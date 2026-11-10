"""Environment access for the Chainlit service: persistence and auth switches.

Everything the chat core needs (LLM keys, A2A URLs, timeouts, quota limits) is
read by the core from the same environment. This module owns the settings that
belong to this service, plus the validation that makes a misconfigured
deployment fail at startup instead of at the first login.
"""

import os
from urllib.parse import urlsplit

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


def google_oauth_enabled() -> bool:
    """Enable the Google button only for a complete provider credential pair."""
    return all(
        (os.getenv(key) or "").strip()
        for key in (
            "OAUTH_GOOGLE_CLIENT_ID",
            "OAUTH_GOOGLE_CLIENT_SECRET",
        )
    )


def google_allowed_emails() -> set[str]:
    """Return the explicit, normalized invitation list; an empty list denies all."""
    return {
        value.strip().lower() for value in os.getenv("PRETE_CHAT_GOOGLE_ALLOWED_EMAILS", "").split(",") if value.strip()
    }


def validate() -> None:
    """Fail loudly on a configuration that cannot work at runtime.

    Raises:
        ConfigurationError: persistence is enabled but no session secret is
            present, so every login would crash with an AssertionError inside
            Chainlit's JWT module; or optional Google login lacks its credential
            pair, persistence, invitations or callback origin.
    """
    if persistence_enabled() and auth_secret() is None:
        raise ConfigurationError(
            f"{AUTH_SECRET_ENV} is required when {DATABASE_URL_ENV} enables persistence and "
            "authentication. Generate one with `openssl rand -hex 32`."
        )
    credentials = [
        (os.getenv(key) or "").strip()
        for key in (
            "OAUTH_GOOGLE_CLIENT_ID",
            "OAUTH_GOOGLE_CLIENT_SECRET",
        )
    ]
    if not any(credentials):
        return
    if not all(credentials) or not persistence_enabled():
        raise ConfigurationError("Google OAuth requires both client credentials and PostgreSQL persistence.")
    allowed = google_allowed_emails()
    if not allowed or any(
        email.count("@") != 1 or not all(email.split("@")) or "*" in email or any(c.isspace() for c in email)
        for email in allowed
    ):
        raise ConfigurationError("PRETE_CHAT_GOOGLE_ALLOWED_EMAILS must contain explicit email addresses.")
    url = urlsplit((os.getenv("CHAINLIT_URL") or "").strip())
    local = url.hostname in {"localhost", "127.0.0.1", "::1"}
    if (
        not url.hostname
        or url.username
        or url.password
        or url.query
        or url.fragment
        or url.path not in {"", "/"}
        or not (url.scheme == "https" or (local and url.scheme == "http"))
    ):
        raise ConfigurationError(
            "Google OAuth requires CHAINLIT_URL as a public HTTPS origin (HTTP allowed on localhost)."
        )
