"""Bearer API-key validation for the OpenAI-compatible surface."""

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from chat_orchestrator.api.auth import get_api_key, require_api_key

VALID_KEY = "test-orchestrator-key"


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("ORCHESTRATOR_API_KEY", VALID_KEY)
    app = FastAPI()

    @app.get("/protected")
    async def protected(_: None = Depends(require_api_key)) -> dict:
        return {"ok": True}

    return TestClient(app)


class TestGetApiKey:
    def test_returns_configured_key(self, monkeypatch):
        monkeypatch.setenv("ORCHESTRATOR_API_KEY", "abc")
        assert get_api_key() == "abc"

    def test_raises_when_unset(self, monkeypatch):
        """Refusing to start beats serving unauthenticated requests."""
        monkeypatch.delenv("ORCHESTRATOR_API_KEY", raising=False)
        with pytest.raises(RuntimeError, match="ORCHESTRATOR_API_KEY"):
            get_api_key()


class TestRequireApiKey:
    def test_accepts_valid_bearer_token(self, client):
        response = client.get("/protected", headers={"Authorization": f"Bearer {VALID_KEY}"})
        assert response.status_code == 200

    def test_rejects_missing_header(self, client):
        assert client.get("/protected").status_code == 401

    def test_rejects_wrong_key(self, client):
        response = client.get("/protected", headers={"Authorization": "Bearer wrong"})
        assert response.status_code == 401

    def test_rejects_wrong_scheme(self, client):
        response = client.get("/protected", headers={"Authorization": f"Basic {VALID_KEY}"})
        assert response.status_code == 401

    def test_rejects_empty_bearer(self, client):
        response = client.get("/protected", headers={"Authorization": "Bearer "})
        assert response.status_code == 401

    def test_rejects_prefix_of_valid_key(self, client):
        """Guards against a startswith-style comparison."""
        response = client.get("/protected", headers={"Authorization": f"Bearer {VALID_KEY[:5]}"})
        assert response.status_code == 401

    def test_401_body_is_italian(self, client):
        body = client.get("/protected").json()
        assert "credenziali" in body["detail"].lower()
