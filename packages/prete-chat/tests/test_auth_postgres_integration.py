"""Postgres-backed auth: hash stays server-side across login persistence.

These tests require ``DATABASE_URL=postgresql+asyncpg://…`` and the Chainlit
schema (``deploy/chainlit/init.sql``). They are skipped in the default unit
matrix and run in the dedicated CI job.
"""

from __future__ import annotations

import os
import uuid

import chainlit as cl
import pytest

from prete_chat import auth, data_layer

pytestmark = pytest.mark.skipif(
    not (os.environ.get("DATABASE_URL") or "").startswith("postgresql"),
    reason="DATABASE_URL=postgresql+asyncpg://… required",
)


@pytest.fixture
async def layer():
    built = data_layer.build()
    assert built is not None
    try:
        yield built
    finally:
        await built.close()


async def _provision(layer, email: str, name: str, password: str) -> str:
    identifier = auth.normalize_identifier(email)
    await layer.create_user(
        cl.User(
            identifier=identifier,
            display_name=name,
            metadata={
                auth.NAME_METADATA_KEY: name,
                auth.PASSWORD_METADATA_KEY: auth.hash_password(password),
            },
        )
    )
    return identifier


class TestPasswordHashServerSide:
    @pytest.mark.asyncio
    async def test_login_sanitize_preserves_hash_and_allows_second_login(self, layer, monkeypatch):
        email = f"don-{uuid.uuid4().hex[:8]}@example.test"
        password = "segreta-integration"
        identifier = await _provision(layer, email, "Don Integration", password)
        stored_before = (await layer.get_user_for_auth(identifier)).metadata[
            auth.PASSWORD_METADATA_KEY
        ]

        monkeypatch.setattr(auth, "get_data_layer", lambda: layer)
        session_user = await auth.password_auth(email, password)
        assert session_user is not None
        assert auth.PASSWORD_METADATA_KEY not in session_user.metadata
        assert "$2" not in str(session_user.metadata)

        # Simulate Chainlit's post-login persistence of the sanitized User.
        await layer.create_user(session_user)

        public = await layer.get_user(identifier)
        assert public is not None
        assert auth.PASSWORD_METADATA_KEY not in public.metadata

        persisted = await layer.get_user_for_auth(identifier)
        assert persisted is not None
        assert persisted.metadata[auth.PASSWORD_METADATA_KEY] == stored_before
        assert auth.verify_password(password, persisted.metadata[auth.PASSWORD_METADATA_KEY])

        again = await auth.password_auth(email, password)
        assert again is not None
        assert auth.PASSWORD_METADATA_KEY not in again.metadata


class TestChainlitHttpUserEndpoint:
    """Optional live Chainlit smoke: set PRETE_CHAT_URL to enable."""

    @pytest.mark.asyncio
    async def test_user_endpoint_never_exposes_password_hash(self, layer, monkeypatch):
        base = os.environ.get("PRETE_CHAT_URL", "").rstrip("/")
        if not base:
            pytest.skip("PRETE_CHAT_URL not set")

        import httpx

        email = f"http-{uuid.uuid4().hex[:8]}@example.test"
        password = "segreta-http"
        await _provision(layer, email, "HTTP User", password)

        async with httpx.AsyncClient(base_url=base, timeout=30.0) as client:
            login = await client.post(
                "/login",
                data={"username": email, "password": password},
            )
            assert login.status_code == 200, login.text
            assert "password_hash" not in login.text
            assert "$2b$" not in login.text and "$2a$" not in login.text

            user = await client.get("/user")
            assert user.status_code == 200, user.text
            body = user.text
            assert "password_hash" not in body
            assert "$2b$" not in body and "$2a$" not in body and "$2y$" not in body
            payload = user.json()
            metadata = payload.get("metadata") or {}
            assert auth.PASSWORD_METADATA_KEY not in metadata

            raw = await layer.get_user_for_auth(auth.normalize_identifier(email))
            assert raw is not None
            assert auth.PASSWORD_METADATA_KEY in raw.metadata
            assert auth.verify_password(password, raw.metadata[auth.PASSWORD_METADATA_KEY])

            # Second login must still succeed (hash not wiped).
            login2 = await client.post(
                "/login",
                data={"username": email, "password": password},
            )
            assert login2.status_code == 200, login2.text
