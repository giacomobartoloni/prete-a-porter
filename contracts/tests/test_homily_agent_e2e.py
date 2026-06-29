"""
End-to-end tests for the Homily Agent A2A protocol.
"""

import httpx
import pytest

from conftest import MOCK_LITURGICAL_DATA


class TestHomilyAgentPing:
    def test_ping(self, homily_url):
        """agent.ping returns pong."""
        resp = httpx.post(homily_url + "/", json={
            "jsonrpc": "2.0", "id": "1", "method": "agent.ping", "params": {},
        })
        assert resp.status_code == 200
        assert resp.json()["result"]["status"] == "pong"


class TestHomilyAgentGenerate:
    def test_generate_homily(self, homily_url):
        """homily.generate returns structured homily with 4 sections."""
        resp = httpx.post(homily_url + "/", json={
            "jsonrpc": "2.0", "id": "2", "method": "homily.generate",
            "params": {
                "liturgical_data": MOCK_LITURGICAL_DATA,
                "occasion": "mass",
                "preferences": {"tone": "conversational", "length": "medium"},
            },
        })
        assert resp.status_code == 200
        result = resp.json()["result"]
        assert result["status"] == "success"
        homily = result["data"]["homily"]
        expected_sections = ("introduction", "reading_reflection", "practical_application", "conclusion")
        for section in expected_sections:
            assert section in homily, f"Missing section: {section}"
            assert len(homily[section]["content"]) > 20

    @pytest.mark.parametrize("occasion", ["mass", "marriage", "baptism", "funeral"])
    def test_generate_homily_occasions(self, homily_url, occasion):
        """homily.generate works for all occasion types."""
        data = dict(MOCK_LITURGICAL_DATA, occasion=occasion)
        resp = httpx.post(homily_url + "/", json={
            "jsonrpc": "2.0", "id": "3", "method": "homily.generate",
            "params": {"liturgical_data": data, "occasion": occasion},
        })
        assert resp.status_code == 200
        assert resp.json()["result"]["status"] == "success"

    def test_generate_homily_missing_data(self, homily_url):
        """homily.generate without liturgical_data returns error."""
        resp = httpx.post(homily_url + "/", json={
            "jsonrpc": "2.0", "id": "4", "method": "homily.generate",
            "params": {"occasion": "mass"},
        })
        assert resp.status_code == 200
        assert "error" in resp.json()


class TestHomilyAgentRefine:
    def test_refine_homily(self, homily_url):
        """homily.refine accepts existing draft and returns refined version."""
        resp = httpx.post(homily_url + "/", json={
            "jsonrpc": "2.0", "id": "5", "method": "homily.refine",
            "params": {
                "liturgical_data": MOCK_LITURGICAL_DATA,
                "occasion": "mass",
                "existing_draft": "Brothers and sisters, today we reflect on the Gospel...",
            },
        })
        assert resp.status_code == 200
        assert resp.json()["result"]["status"] == "success"


class TestHomilyAgentAdjustTone:
    def test_adjust_tone(self, homily_url):
        """homily.adjust_tone returns homily with adjusted tone."""
        resp = httpx.post(homily_url + "/", json={
            "jsonrpc": "2.0", "id": "6", "method": "homily.adjust_tone",
            "params": {
                "liturgical_data": MOCK_LITURGICAL_DATA,
                "occasion": "mass",
                "preferences": {"tone": "celebratory"},
            },
        })
        assert resp.status_code == 200
        assert resp.json()["result"]["status"] == "success"


class TestHomilyAgentErrors:
    def test_unknown_method(self, homily_url):
        """Unknown method returns error."""
        resp = httpx.post(homily_url + "/", json={
            "jsonrpc": "2.0", "id": "7", "method": "nonexistent.method", "params": {},
        })
        assert resp.status_code == 200
        assert "error" in resp.json()
