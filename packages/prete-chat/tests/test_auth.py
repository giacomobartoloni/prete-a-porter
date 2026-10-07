"""Password authentication: bcrypt verification against the persisted hash."""

import pytest
from chainlit.user import PersistedUser

from prete_chat import auth


class _FakeLayer:
    def __init__(self, user: PersistedUser | None = None):
        self.user = user
        self.queried: list[str] = []

    async def get_user(self, identifier: str) -> PersistedUser | None:
        # Public getter: session-safe (no password_hash).
        if self.user is None:
            return None
        metadata = {
            k: v
            for k, v in (self.user.metadata or {}).items()
            if k != auth.PASSWORD_METADATA_KEY
        }
        return PersistedUser(
            id=self.user.id,
            identifier=self.user.identifier,
            createdAt=self.user.createdAt,
            display_name=self.user.display_name,
            metadata=metadata,
        )

    async def get_user_for_auth(self, identifier: str) -> PersistedUser | None:
        self.queried.append(identifier)
        return self.user


def _persisted(identifier: str = "don@example.com", name: str = "Don Mario", password: str = "segreta") -> PersistedUser:
    return PersistedUser(
        id="00000000-0000-0000-0000-000000000001",
        identifier=identifier,
        createdAt="2026-09-18T00:00:00Z",
        metadata={
            auth.NAME_METADATA_KEY: name,
            auth.PASSWORD_METADATA_KEY: auth.hash_password(password),
        },
    )


class TestHashing:
    def test_round_trip(self):
        hashed = auth.hash_password("segreta")
        assert hashed != "segreta"
        assert auth.verify_password("segreta", hashed) is True

    def test_wrong_password_does_not_match(self):
        assert auth.verify_password("sbagliata", auth.hash_password("segreta")) is False

    def test_malformed_hash_never_matches(self):
        assert auth.verify_password("segreta", "not-a-hash") is False


class TestNormalizeIdentifier:
    def test_lowercases_and_strips(self):
        assert auth.normalize_identifier("  Don@Example.COM ") == "don@example.com"


class TestPasswordAuth:
    @pytest.mark.asyncio
    async def test_valid_credentials_return_the_user_without_the_password_hash(self, monkeypatch):
        monkeypatch.setattr(auth, "get_data_layer", lambda: _FakeLayer(_persisted()))

        user = await auth.password_auth("Don@Example.com", "segreta")

        assert user is not None
        assert user.identifier == "don@example.com"
        assert user.display_name == "Don Mario"
        assert auth.PASSWORD_METADATA_KEY not in user.metadata
        assert user.metadata[auth.NAME_METADATA_KEY] == "Don Mario"

    @pytest.mark.asyncio
    async def test_password_auth_never_returns_password_hash_in_user_metadata(self, monkeypatch):
        """Security: the JWT/session User must never carry the bcrypt hash."""
        monkeypatch.setattr(auth, "get_data_layer", lambda: _FakeLayer(_persisted()))

        user = await auth.password_auth("don@example.com", "segreta")

        assert user is not None
        assert auth.PASSWORD_METADATA_KEY not in (user.metadata or {})
        serialized = str(user.metadata)
        assert "$2" not in serialized
        assert "password_hash" not in serialized

    @pytest.mark.asyncio
    async def test_identifier_is_normalised_before_the_lookup(self, monkeypatch):
        layer = _FakeLayer(_persisted())
        monkeypatch.setattr(auth, "get_data_layer", lambda: layer)

        await auth.password_auth("  Don@Example.com ", "segreta")

        assert layer.queried == ["don@example.com"]

    @pytest.mark.asyncio
    async def test_wrong_password_returns_none(self, monkeypatch):
        monkeypatch.setattr(auth, "get_data_layer", lambda: _FakeLayer(_persisted()))
        assert await auth.password_auth("don@example.com", "sbagliata") is None

    @pytest.mark.asyncio
    async def test_unknown_user_returns_none(self, monkeypatch):
        monkeypatch.setattr(auth, "get_data_layer", lambda: _FakeLayer(None))
        assert await auth.password_auth("nessuno@example.com", "segreta") is None

    @pytest.mark.asyncio
    async def test_no_data_layer_returns_none(self, monkeypatch):
        monkeypatch.setattr(auth, "get_data_layer", lambda: None)
        assert await auth.password_auth("don@example.com", "segreta") is None

    @pytest.mark.asyncio
    async def test_user_without_a_stored_hash_cannot_log_in(self, monkeypatch):
        user = _persisted()
        user.metadata.pop(auth.PASSWORD_METADATA_KEY)
        monkeypatch.setattr(auth, "get_data_layer", lambda: _FakeLayer(user))
        assert await auth.password_auth("don@example.com", "segreta") is None
