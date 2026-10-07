"""Persistence and auth switches: explicit env gating, loud misconfiguration."""

import pytest

from prete_chat import config


class TestDatabaseUrl:
    def test_postgres_url_enables_persistence(self, monkeypatch):
        monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://chainlit:pw@prete-chat-db:5432/chainlit")
        assert config.persistence_enabled() is True
        assert config.database_url().startswith("postgresql+asyncpg://")

    def test_legacy_file_url_is_treated_as_disabled(self, monkeypatch):
        """The repository .env carries the retiring frontend's Prisma URL."""
        monkeypatch.setenv("DATABASE_URL", "file:./dev.db")
        assert config.database_url() is None
        assert config.persistence_enabled() is False

    def test_missing_url_disables_persistence(self, monkeypatch):
        monkeypatch.delenv("DATABASE_URL", raising=False)
        assert config.database_url() is None


class TestValidate:
    def test_persistence_without_auth_secret_fails_loudly(self, monkeypatch):
        monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://chainlit:pw@db:5432/chainlit")
        monkeypatch.delenv("CHAINLIT_AUTH_SECRET", raising=False)
        with pytest.raises(config.ConfigurationError):
            config.validate()

    def test_persistence_with_auth_secret_is_valid(self, monkeypatch):
        monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://chainlit:pw@db:5432/chainlit")
        monkeypatch.setenv("CHAINLIT_AUTH_SECRET", "secret")
        config.validate()

    def test_poc_mode_needs_no_auth_secret(self, monkeypatch):
        monkeypatch.delenv("DATABASE_URL", raising=False)
        monkeypatch.delenv("CHAINLIT_AUTH_SECRET", raising=False)
        config.validate()
