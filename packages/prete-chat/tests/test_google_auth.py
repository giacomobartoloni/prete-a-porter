"""Google login policy uses verified provider identity and preserves account keys."""

import chainlit as cl
import pytest
from chainlit.user import PersistedUser

from prete_chat import auth, config


class UserStore:
    def __init__(self, metadata=None):
        self.metadata = metadata

    async def get_user(self, identifier):
        if self.metadata is None:
            return None
        return PersistedUser(
            id="existing-id", identifier=identifier, createdAt="2026-10-17T00:00:00Z", metadata=self.metadata
        )

    async def create_user(self, user):
        return user


@pytest.fixture
def google(monkeypatch):
    monkeypatch.setenv("PRETE_CHAT_GOOGLE_ALLOWED_EMAILS", " Don@Example.com , other@example.com ")
    monkeypatch.setattr(auth, "get_data_layer", lambda: UserStore())
    return {
        "id": "google-123",
        "email": "Don@Example.COM",
        "verified_email": True,
        "name": "Don Mario",
        "picture": "https://example.com/photo",
    }


async def authenticate(payload, provider="google"):
    # Framework defaults must not define identity or leak into session metadata.
    return await auth.google_oauth(
        provider, "secret-token", payload, cl.User(identifier="wrong@example.com", metadata={"password_hash": "secret"})
    )


async def test_verified_allowlisted_google_user_has_canonical_identity(google):
    user = await authenticate(google)
    assert user is not None
    assert user.identifier == "don@example.com"
    assert user.display_name == "Don Mario"
    assert user.metadata == {
        "name": "Don Mario",
        "provider": "google",
        "google_id": "google-123",
        "image": "https://example.com/photo",
    }


@pytest.mark.parametrize(
    "changes",
    [
        {"verified_email": False},
        {"verified_email": "true"},
        {"verified_email": None},
        {"email": "uninvited@example.com"},
        {"email": ""},
        {"email": None},
        {"id": ""},
        {"id": None},
    ],
)
async def test_invalid_or_uninvited_identity_is_rejected(google, changes):
    assert await authenticate(google | changes) is None


async def test_other_provider_is_rejected(google):
    assert await authenticate(google, "github") is None


async def test_no_allowlist_fails_closed(google, monkeypatch):
    monkeypatch.delenv("PRETE_CHAT_GOOGLE_ALLOWED_EMAILS")
    assert await authenticate(google) is None


async def test_google_requires_persistence(google, monkeypatch):
    monkeypatch.setattr(auth, "get_data_layer", lambda: None)
    assert await authenticate(google) is None


async def test_google_denied_if_atomic_persistence_fails(google, monkeypatch):
    class FailedStore(UserStore):
        async def create_user(self, user):
            return None

    monkeypatch.setattr(auth, "get_data_layer", lambda: FailedStore())
    assert await authenticate(google) is None


async def test_google_subject_cannot_change_for_linked_account(google, monkeypatch):
    monkeypatch.setattr(auth, "get_data_layer", lambda: UserStore({"google_id": "different"}))
    assert await authenticate(google) is None


async def test_existing_password_account_links_without_exposing_credentials(google, monkeypatch):
    monkeypatch.setattr(auth, "get_data_layer", lambda: UserStore({"name": "Existing"}))
    user = await authenticate(google)
    assert user.identifier == "don@example.com"
    assert "password_hash" not in user.metadata


@pytest.fixture
def oauth_env(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://user:pw@db/app")
    monkeypatch.setenv("CHAINLIT_AUTH_SECRET", "test-secret")
    monkeypatch.setenv("CHAINLIT_URL", "http://localhost:3003")
    monkeypatch.setenv("OAUTH_GOOGLE_CLIENT_ID", "test-client")
    monkeypatch.setenv("OAUTH_GOOGLE_CLIENT_SECRET", "test-client-secret")
    monkeypatch.setenv("PRETE_CHAT_GOOGLE_ALLOWED_EMAILS", "don@example.com")


@pytest.mark.parametrize(
    "key,value",
    [
        ("OAUTH_GOOGLE_CLIENT_ID", ""),
        ("OAUTH_GOOGLE_CLIENT_SECRET", ""),
        ("PRETE_CHAT_GOOGLE_ALLOWED_EMAILS", ""),
        ("PRETE_CHAT_GOOGLE_ALLOWED_EMAILS", "*,@example.com"),
        ("DATABASE_URL", ""),
        ("CHAINLIT_URL", ""),
        ("CHAINLIT_URL", "https://app.example.com/auth"),
        ("CHAINLIT_URL", "http://public.example.com"),
    ],
)
def test_incomplete_oauth_setup_fails_at_startup(oauth_env, monkeypatch, key, value):
    monkeypatch.setenv(key, value)
    with pytest.raises(config.ConfigurationError):
        config.validate()


def test_complete_oauth_setup_is_valid(oauth_env):
    config.validate()
    assert config.google_oauth_enabled()
