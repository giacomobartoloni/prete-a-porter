"""Contract auth helpers must preserve exact credential bytes."""

from __future__ import annotations

import base64
import importlib

import pytest


def test_a2a_auth_headers_preserve_padded_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("A2A_BASIC_AUTH_USERNAME", " a2a-test ")
    monkeypatch.setenv("A2A_BASIC_AUTH_PASSWORD", " padded-secret ")
    import conftest as contracts_conftest

    importlib.reload(contracts_conftest)
    headers = contracts_conftest.a2a_auth_headers()
    assert "Authorization" in headers
    decoded = base64.b64decode(headers["Authorization"].removeprefix("Basic ")).decode()
    assert decoded == " a2a-test : padded-secret "


def test_a2a_auth_headers_reject_whitespace_only(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("A2A_BASIC_AUTH_USERNAME", "   ")
    monkeypatch.setenv("A2A_BASIC_AUTH_PASSWORD", "padded-secret")
    import conftest as contracts_conftest

    importlib.reload(contracts_conftest)
    assert contracts_conftest.a2a_auth_headers() == {}
