"""Fail-closed Basic Auth for normal A2A HTTP execution."""

from __future__ import annotations

import base64
import os

import pytest
from fastapi.testclient import TestClient

from a2a_protocol.server import A2AServer, resolve_basic_auth_credentials


DISPOSABLE_USER = "a2a-test"
DISPOSABLE_PASS = "a2a-test-secret"


async def _handler(method: str, params: dict) -> dict:
    return {"status": "ok", "method": method}


def _auth_header(user: str, password: str) -> dict[str, str]:
    token = base64.b64encode(f"{user}:{password}".encode()).decode()
    return {"Authorization": f"Basic {token}"}


@pytest.fixture(autouse=True)
def _clear_auth_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("A2A_BASIC_AUTH_USERNAME", raising=False)
    monkeypatch.delenv("A2A_BASIC_AUTH_PASSWORD", raising=False)
    monkeypatch.delenv("A2A_ALLOW_UNAUTHENTICATED", raising=False)


def test_resolve_rejects_missing_pair() -> None:
    with pytest.raises(ValueError, match="complete"):
        resolve_basic_auth_credentials(None, None)


def test_resolve_rejects_username_only() -> None:
    with pytest.raises(ValueError, match="partial"):
        resolve_basic_auth_credentials(DISPOSABLE_USER, None)


def test_resolve_rejects_password_only() -> None:
    with pytest.raises(ValueError, match="partial"):
        resolve_basic_auth_credentials(None, DISPOSABLE_PASS)


def test_resolve_rejects_blank_as_incomplete() -> None:
    with pytest.raises(ValueError, match="partial|complete"):
        resolve_basic_auth_credentials("  ", DISPOSABLE_PASS)


def test_resolve_accepts_complete_pair() -> None:
    user, password = resolve_basic_auth_credentials(DISPOSABLE_USER, DISPOSABLE_PASS)
    assert user == DISPOSABLE_USER
    assert password == DISPOSABLE_PASS


def test_resolve_explicit_unauthenticated_mode_allows_empty_pair() -> None:
    assert resolve_basic_auth_credentials(
        None, None, allow_unauthenticated=True
    ) == (None, None)


def test_resolve_explicit_unauthenticated_mode_still_rejects_partial() -> None:
    with pytest.raises(ValueError, match="partial"):
        resolve_basic_auth_credentials(
            DISPOSABLE_USER, None, allow_unauthenticated=True
        )


def test_create_fastapi_app_requires_complete_credentials() -> None:
    server = A2AServer(handler=_handler, name="auth_test")
    with pytest.raises(ValueError, match="complete|partial"):
        server.create_fastapi_app()


def test_create_fastapi_app_rejects_partial_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("A2A_BASIC_AUTH_USERNAME", DISPOSABLE_USER)
    server = A2AServer(handler=_handler, name="auth_test")
    with pytest.raises(ValueError, match="partial"):
        server.create_fastapi_app()


def test_protected_routes_reject_missing_auth() -> None:
    server = A2AServer(
        handler=_handler,
        name="auth_test",
        basic_auth_username=DISPOSABLE_USER,
        basic_auth_password=DISPOSABLE_PASS,
    )
    client = TestClient(server.create_fastapi_app())
    for path, method in (
        ("/", "post"),
        ("/message:send", "post"),
        ("/tasks", "get"),
        ("/.well-known/agent-card.json", "get"),
    ):
        if method == "post":
            resp = client.post(path, json={"jsonrpc": "2.0", "id": "1", "method": "x"})
        else:
            resp = client.get(path)
        assert resp.status_code == 401, path


def test_protected_routes_reject_wrong_credentials() -> None:
    server = A2AServer(
        handler=_handler,
        name="auth_test",
        basic_auth_username=DISPOSABLE_USER,
        basic_auth_password=DISPOSABLE_PASS,
    )
    client = TestClient(server.create_fastapi_app())
    resp = client.get(
        "/.well-known/agent-card.json",
        headers=_auth_header("wrong", "creds"),
    )
    assert resp.status_code == 401


def test_protected_routes_reject_malformed_auth_header() -> None:
    server = A2AServer(
        handler=_handler,
        name="auth_test",
        basic_auth_username=DISPOSABLE_USER,
        basic_auth_password=DISPOSABLE_PASS,
    )
    client = TestClient(server.create_fastapi_app())
    resp = client.get(
        "/.well-known/agent-card.json",
        headers={"Authorization": "Basic not-base64"},
    )
    assert resp.status_code == 401


def test_health_remains_public_without_credentials() -> None:
    server = A2AServer(
        handler=_handler,
        name="auth_test",
        basic_auth_username=DISPOSABLE_USER,
        basic_auth_password=DISPOSABLE_PASS,
    )
    client = TestClient(server.create_fastapi_app())
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "healthy"


def test_matching_credentials_allow_agent_card() -> None:
    server = A2AServer(
        handler=_handler,
        name="auth_test",
        basic_auth_username=DISPOSABLE_USER,
        basic_auth_password=DISPOSABLE_PASS,
    )
    client = TestClient(server.create_fastapi_app())
    resp = client.get(
        "/.well-known/agent-card.json",
        headers=_auth_header(DISPOSABLE_USER, DISPOSABLE_PASS),
    )
    assert resp.status_code == 200
