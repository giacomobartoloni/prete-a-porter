"""The real app serves the OpenAI-compatible routes."""

from fastapi.testclient import TestClient

from chat_orchestrator.main import app


class TestRouterMounting:
    def test_models_route_is_mounted(self):
        assert TestClient(app).get("/v1/models").status_code == 200

    def test_chat_completions_route_is_mounted(self):
        """A malformed body proves the route exists (422, not 404)."""
        response = TestClient(app).post("/v1/chat/completions", json={})
        assert response.status_code == 422

    def test_health_still_works(self):
        assert TestClient(app).get("/health").status_code == 200

    def test_websocket_route_still_registered(self):
        paths = {getattr(route, "path", None) for route in app.routes}
        assert "/ws/chat/{session_id}" in paths
