"""The data layer serializes every statement; concurrent writes must not race.

Regression guard for the live defect: Chainlit schedules step/message writes as
independent tasks, and the bundled layer's fresh-session-per-statement pattern
interleaved ``session.begin()`` calls on asyncpg until writes were dropped
(persisted answers with empty output, missing tool steps).

Also preserves the server-side password hash when Chainlit re-persists a
sanitized session User after login.
"""

import asyncio

import chainlit as cl
import pytest
from chainlit.data.sql_alchemy import SQLAlchemyDataLayer
from chainlit.user import PersistedUser

from prete_chat import auth
from prete_chat.data_layer import SerializedSQLAlchemyDataLayer, build


class TestBuild:
    def test_no_url_builds_nothing(self, monkeypatch):
        monkeypatch.delenv("DATABASE_URL", raising=False)
        assert build() is None

    def test_postgres_url_builds_the_serialized_layer(self, monkeypatch):
        monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://chainlit:pw@prete-chat-db:5432/chainlit")
        layer = build()
        try:
            assert isinstance(layer, SerializedSQLAlchemyDataLayer)
        finally:
            asyncio.run(layer.close())


class TestStatementSerialization:
    def test_concurrent_statements_never_overlap(self, monkeypatch):
        layer = SerializedSQLAlchemyDataLayer(conninfo="postgresql+asyncpg://chainlit:pw@localhost:5432/chainlit")
        overlap = {"now": 0, "max": 0}

        async def probe(self, query, parameters):
            overlap["now"] += 1
            overlap["max"] = max(overlap["max"], overlap["now"])
            await asyncio.sleep(0.01)
            overlap["now"] -= 1
            return None

        monkeypatch.setattr(SQLAlchemyDataLayer, "execute_sql", probe)

        async def run() -> None:
            await asyncio.gather(*(layer.execute_sql("SELECT 1", {}) for _ in range(5)))
            await layer.close()

        asyncio.run(run())
        assert overlap["max"] == 1


class TestCreateUser:
    @pytest.mark.asyncio
    async def test_persistence_return_and_input_remain_session_safe(self, monkeypatch):
        layer = SerializedSQLAlchemyDataLayer(conninfo="postgresql+asyncpg://u:pw@localhost/db")
        stored_hash = auth.hash_password("password")

        async def execute(query, parameters):
            return [{"id": "00000000-0000-0000-0000-000000000001",
                     "identifier": "don@example.com", "createdAt": "2026-10-17",
                     "metadata": {"name": "Don Mario", "password_hash": stored_hash, "google_id": "subject"}}]

        monkeypatch.setattr(layer, "execute_sql", execute)
        user = cl.User(identifier="don@example.com", metadata={"name": "Don Mario"})
        try:
            result = await layer.create_user(user)
            assert auth.PASSWORD_METADATA_KEY not in result.metadata
            assert result.metadata["google_id"] == "subject"
            assert user.metadata == {"name": "Don Mario"}
        finally:
            await layer.close()

    @pytest.mark.asyncio
    @pytest.mark.parametrize("rows", [None, []])
    async def test_failed_or_conflicting_write_returns_no_user(self, monkeypatch, rows):
        layer = SerializedSQLAlchemyDataLayer(conninfo="postgresql+asyncpg://u:pw@localhost/db")

        async def execute(query, parameters):
            return rows

        monkeypatch.setattr(layer, "execute_sql", execute)
        try:
            assert await layer.create_user(cl.User(identifier="don@example.com")) is None
        finally:
            await layer.close()


class TestPublicVersusAuthGetters:
    @pytest.mark.asyncio
    async def test_public_get_user_strips_password_hash(self, monkeypatch):
        layer = SerializedSQLAlchemyDataLayer(
            conninfo="postgresql+asyncpg://chainlit:pw@localhost:5432/chainlit"
        )
        stored_hash = auth.hash_password("segreta")
        raw = PersistedUser(
            id="00000000-0000-0000-0000-000000000002",
            identifier="don@example.com",
            createdAt="2026-09-18T00:00:00Z",
            display_name="Don Mario",
            metadata={
                auth.NAME_METADATA_KEY: "Don Mario",
                auth.PASSWORD_METADATA_KEY: stored_hash,
            },
        )

        async def fake_get_user(self, identifier: str):
            return raw

        monkeypatch.setattr(SQLAlchemyDataLayer, "get_user", fake_get_user)

        public = await layer.get_user("don@example.com")
        private = await layer.get_user_for_auth("don@example.com")

        assert public is not None
        assert auth.PASSWORD_METADATA_KEY not in public.metadata
        assert public.metadata[auth.NAME_METADATA_KEY] == "Don Mario"
        assert private is not None
        assert private.metadata[auth.PASSWORD_METADATA_KEY] == stored_hash
        # Raw object must not be mutated.
        assert auth.PASSWORD_METADATA_KEY in raw.metadata
        await layer.close()
