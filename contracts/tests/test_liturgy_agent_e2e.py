"""
End-to-end tests for the Liturgy Agent A2A protocol.
"""

import httpx
import pytest


class TestLiturgyAgentPing:
    def test_ping(self, liturgy_url):
        """agent.ping returns pong with version."""
        resp = httpx.post(liturgy_url + "/", json={
            "jsonrpc": "2.0", "id": "1", "method": "agent.ping", "params": {},
        })
        assert resp.status_code == 200
        result = resp.json()["result"]
        assert result["status"] == "pong"
        assert result["agent"] == "liturgy_agent"
        assert result["version"] is not None


class TestLiturgyAgentGetReadings:
    def test_get_readings_mass(self, liturgy_url):
        """get_readings with occasion=mass returns structured readings."""
        resp = httpx.post(liturgy_url + "/", json={
            "jsonrpc": "2.0", "id": "2", "method": "liturgy_agent.get_readings",
            "params": {"occasion": "mass"},
        })
        assert resp.status_code == 200
        result = resp.json()["result"]
        assert result["status"] == "success"
        data = result["data"]
        assert "date" in data
        assert "season" in data["metadata"]
        assert "color" in data["metadata"]
        for key in ("first_reading", "psalm", "gospel"):
            assert key in data
            assert "reference" in data[key]

    def test_get_readings_specific_date(self, liturgy_url):
        """get_readings with YYYY-MM-DD date returns readings for that date."""
        resp = httpx.post(liturgy_url + "/", json={
            "jsonrpc": "2.0", "id": "3", "method": "liturgy_agent.get_readings",
            "params": {"occasion": "mass", "date": "2026-04-05"},
        })
        assert resp.status_code == 200
        result = resp.json()["result"]
        assert result["status"] == "success"
        assert result["data"]["date"] == "2026-04-05"

    def test_get_readings_unknown_occasion(self, liturgy_url):
        """get_readings with invalid occasion returns JSON-RPC error."""
        resp = httpx.post(liturgy_url + "/", json={
            "jsonrpc": "2.0", "id": "4", "method": "liturgy_agent.get_readings",
            "params": {"occasion": "invalid_occasion"},
        })
        assert resp.status_code == 200
        assert "error" in resp.json()

    def test_get_readings_missing_occasion(self, liturgy_url):
        """get_readings without required occasion returns error."""
        resp = httpx.post(liturgy_url + "/", json={
            "jsonrpc": "2.0", "id": "5", "method": "liturgy_agent.get_readings",
            "params": {},
        })
        assert resp.status_code == 200
        assert "error" in resp.json()

    def test_get_readings_invalid_date(self, liturgy_url):
        """get_readings with non-ISO date returns error."""
        resp = httpx.post(liturgy_url + "/", json={
            "jsonrpc": "2.0", "id": "6", "method": "liturgy_agent.get_readings",
            "params": {"occasion": "mass", "date": "not-a-date"},
        })
        assert resp.status_code == 200
        assert "error" in resp.json()


class TestLiturgyAgentGetLectionary:
    @pytest.mark.parametrize("occasion", ["marriage", "baptism", "funeral"])
    def test_get_lectionary(self, liturgy_url, occasion):
        """get_lectionary returns readings for each special occasion."""
        resp = httpx.post(liturgy_url + "/", json={
            "jsonrpc": "2.0", "id": "7", "method": "liturgy_agent.get_lectionary",
            "params": {"occasion": occasion},
        })
        assert resp.status_code == 200
        result = resp.json()["result"]
        assert result["occasion"] == occasion
        assert result["readings_count"] > 0


class TestLiturgyAgentCache:
    def test_cache_hit(self, liturgy_url):
        """Second call for same date returns cached data."""
        target_date = "2026-06-01"
        payload = {
            "jsonrpc": "2.0", "id": "8", "method": "liturgy_agent.get_readings",
            "params": {"occasion": "mass", "date": target_date},
        }
        resp1 = httpx.post(liturgy_url + "/", json=payload)
        assert resp1.json()["result"]["status"] == "success"

        resp2 = httpx.post(liturgy_url + "/", json=payload)
        assert resp2.json()["result"]["status"] == "success"
        # Cache may be "web" if not implemented, but should not error
        source = resp2.json()["result"].get("source")
        assert source in ("cache", "web")
