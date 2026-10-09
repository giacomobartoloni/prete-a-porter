"""Fail-closed Basic Auth for normal A2A HTTP execution."""

from __future__ import annotations

import base64
import os

import pytest
from fastapi.testclient import TestClient

from a2a_protocol.server import A2AServer, resolve_basic_auth_credentials
from a2a_protocol.transport import HTTPTransport


DISPOSABLE_USER = "a2a-test"
DISPOSABLE_PASS = "a2a-test-secret"


@pytest.mark.parametrize("username,password", [
    ("user", None), (None, "secret"), ("   ", "secret"), ("user", "   "),
])
def test_transport_rejects_partial_resolved_auth(monkeypatch, username, password):
    monkeypatch.delenv("A2A_BASIC_AUTH_USERNAME", raising=False)
    monkeypatch.delenv("A2A_BASIC_AUTH_PASSWORD", raising=False)
    with pytest.raises(ValueError, match="both|pair"):
        HTTPTransport("http://localhost:1", auth_username=username, auth_password=password)


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


def test_resolve_preserves_padded_credential_bytes() -> None:
    """Configured padding is significant; strip only to reject whitespace-only."""
    padded_user = " a2a-test "
    padded_pass = " padded-secret "
    user, password = resolve_basic_auth_credentials(padded_user, padded_pass)
    assert user == padded_user
    assert password == padded_pass


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


def test_padded_credentials_exact_header_succeeds_trimmed_fails() -> None:
    """Production transport must send exact bytes; trimmed password must 401."""
    padded_user = " a2a-test "
    padded_pass = " padded-secret "
    server = A2AServer(
        handler=_handler,
        name="auth_test",
        basic_auth_username=padded_user,
        basic_auth_password=padded_pass,
    )
    client = TestClient(server.create_fastapi_app())
    ok = client.get(
        "/.well-known/agent-card.json",
        headers=_auth_header(padded_user, padded_pass),
    )
    assert ok.status_code == 200
    trimmed = client.get(
        "/.well-known/agent-card.json",
        headers=_auth_header(padded_user.strip(), padded_pass.strip()),
    )
    assert trimmed.status_code == 401
