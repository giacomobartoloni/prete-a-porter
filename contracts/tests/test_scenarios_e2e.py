"""
Multi-step user scenario end-to-end tests.
"""

import httpx
import pytest

from conftest import MOCK_LITURGICAL_DATA


class TestFullFlow:
    def test_readings_then_homily(self, liturgy_url, homily_url):
        """Full flow: get readings from liturgy agent, then generate homily."""
        resp = httpx.post(liturgy_url + "/", json={
            "jsonrpc": "2.0", "id": "1", "method": "liturgy_agent.get_readings",
            "params": {"occasion": "mass"},
        })
        assert resp.status_code == 200
        result = resp.json()["result"]
        assert result["status"] == "success"
        readings = result["data"]

        resp = httpx.post(homily_url + "/", json={
            "jsonrpc": "2.0", "id": "2", "method": "homily.generate",
            "params": {
                "liturgical_data": readings,
                "occasion": "mass",
                "preferences": {"tone": "conversational", "length": "medium"},
            },
        })
        assert resp.status_code == 200
        homily_result = resp.json()["result"]
        assert homily_result["status"] == "success"
        homily = homily_result["data"]["homily"]
        assert homily["introduction"]["content"] is not None

    def test_wedding_flow(self, liturgy_url, homily_url):
        """Wedding flow: lectionary → homily generation."""
        resp = httpx.post(liturgy_url + "/", json={
            "jsonrpc": "2.0", "id": "1", "method": "liturgy_agent.get_lectionary",
            "params": {"occasion": "marriage"},
        })
        assert resp.status_code == 200
        lectionary_result = resp.json()["result"]
        assert "lectionary" in lectionary_result

        resp = httpx.post(homily_url + "/", json={
            "jsonrpc": "2.0", "id": "2", "method": "homily.generate",
            "params": {
                "liturgical_data": MOCK_LITURGICAL_DATA,
                "occasion": "marriage",
                "preferences": {"tone": "celebratory"},
            },
        })
        assert resp.status_code == 200
        assert resp.json()["result"]["status"] == "success"

    def test_error_recovery(self, liturgy_url):
        """Error on bad request, then success on corrected request."""
        resp1 = httpx.post(liturgy_url + "/", json={
            "jsonrpc": "2.0", "id": "1", "method": "liturgy_agent.get_readings",
            "params": {},
        })
        assert resp1.status_code == 200
        assert "error" in resp1.json()

        resp2 = httpx.post(liturgy_url + "/", json={
            "jsonrpc": "2.0", "id": "2", "method": "liturgy_agent.get_readings",
            "params": {"occasion": "mass"},
        })
        assert resp2.status_code == 200
        result = resp2.json()["result"]
        assert result["status"] == "success"
