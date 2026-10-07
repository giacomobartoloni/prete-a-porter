"""The real app serves the OpenAI-compatible routes, behind the API key."""

import pytest
from fastapi.testclient import TestClient

from chat_orchestrator.main import app

AUTH_HEADERS = {"Authorization": "Bearer test-orchestrator-key"}


@pytest.fixture(autouse=True)
def _set_api_key(monkeypatch):
    monkeypatch.setenv("ORCHESTRATOR_API_KEY", "test-orchestrator-key")


class TestRouterMounting:
    def test_models_route_is_mounted(self):
        response = TestClient(app).get("/v1/models", headers=AUTH_HEADERS)
        assert response.status_code == 200

    def test_chat_completions_route_is_mounted(self):
        """A malformed body proves the route exists (422, not 404)."""
        response = TestClient(app).post("/v1/chat/completions", json={}, headers=AUTH_HEADERS)
        assert response.status_code == 422

    def test_unauthenticated_request_is_rejected(self):
        """The gate is applied to the real app, not only to the test app."""
        assert TestClient(app).get("/v1/models").status_code == 401

    def test_health_still_works(self):
        assert TestClient(app).get("/health").status_code == 200

    def test_websocket_route_still_registered(self):
        paths = {getattr(route, "path", None) for route in app.routes}
        assert "/ws/chat/{session_id}" in paths
