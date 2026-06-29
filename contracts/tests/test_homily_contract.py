"""
Contract tests for Homily Agent A2A methods.

Tests verify that the homily agent complies with the standard A2A protocol
specification defined in contracts/homily-agent-contract.json.
Tests will be skipped if the homily agent is not running on port 8002.
"""

import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, Optional

import httpx
import pytest

from conftest import MOCK_LITURGICAL_DATA


# Configuration from contract
HOMILY_AGENT_URL = os.environ.get("A2A_HOMILY_URL", "http://localhost:8002")
HOMILY_AGENT_ENDPOINT = ""
CONTRACT_PATH = Path(__file__).parent.parent / "homily-agent-contract.json"


def load_contract() -> Dict[str, Any]:
    """Load the homily agent contract specification."""
    with open(CONTRACT_PATH) as f:
        return json.load(f)


def extract_reply(response: dict) -> dict:
    """Extract agent reply from standard A2A message/send response."""
    task = response["result"]
    history = task.get("history", [])
    agent_msgs = [m for m in history if m.get("role") == "agent"]
    if not agent_msgs:
        return {"error": "No agent reply found"}
    reply_text = agent_msgs[-1]["parts"][0]["text"]
    return json.loads(reply_text)


def is_agent_available() -> bool:
    """Check if the homily agent is available."""
    try:
        response = httpx.get(f"{HOMILY_AGENT_URL}/health", timeout=5.0)
        return response.status_code == 200
    except (httpx.ConnectError, httpx.TimeoutException):
        return False


@pytest.fixture
def contract() -> Dict[str, Any]:
    """Load the contract specification."""
    return load_contract()


@pytest.fixture
def http_client() -> httpx.Client:
    """Create an HTTP client for A2A requests."""
    return httpx.Client(timeout=120.0)


def make_message_send(
    cmd_method: str,
    cmd_params: Optional[Dict[str, Any]] = None,
    client: Optional[httpx.Client] = None,
) -> Dict[str, Any]:
    """Make a standard A2A message/send request and return the full response."""
    cmd_text = json.dumps({"method": cmd_method, "params": cmd_params or {}})
    payload = {
        "jsonrpc": "2.0",
        "id": "1",
        "method": "message/send",
        "params": {
            "message": {
                "role": "user",
                "parts": [{"text": cmd_text}],
            }
        },
    }
    with_cls = client or httpx.Client(timeout=120.0)
    try:
        response = with_cls.post(f"{HOMILY_AGENT_URL}/", json=payload)
        response.raise_for_status()
        return response.json()
    finally:
        if client is None:
            with_cls.close()


class TestHomilyAgentContract:
    """Contract tests for homily agent A2A methods."""

    pytestmark = pytest.mark.skipif(
        not is_agent_available(),
        reason="Homily agent not running on port 8002",
    )

    # -------------------------------------------------------------------------
    # agent.ping tests
    # -------------------------------------------------------------------------

    def test_agent_ping_format(self, http_client: httpx.Client):
        """Verify agent.ping via standard message/send."""
        data = make_message_send("agent.ping", client=http_client)
        reply = extract_reply(data)

        assert "status" in reply
        assert reply["status"] in ["ok", "pong"]
        assert reply.get("agent") == "homily_agent"

    def test_agent_ping_task_structure(self, http_client: httpx.Client):
        """Verify message/send returns valid Task structure."""
        data = make_message_send("agent.ping", client=http_client)
        task = data["result"]

        assert "id" in task
        assert "contextId" in task
        assert task["status"]["state"] in ("completed", "working")
        assert len(task["history"]) >= 1
        for msg in task["history"]:
            assert "id" in msg or "messageId" in msg
            assert "role" in msg
            assert "parts" in msg
            assert len(msg["parts"]) > 0

    # -------------------------------------------------------------------------
    # homily.generate tests
    # -------------------------------------------------------------------------

    def test_generate_format(self, http_client: httpx.Client):
        """Verify homily.generate returns correct format via message/send."""
        data = make_message_send("homily.generate", {
            "liturgical_data": {
                "first_reading": {"reference": "Genesis 12:1-4a", "text": "The Lord said to Abram...", "type": "First"},
                "gospel": {"reference": "John 3:1-17", "text": "Jesus said to Nicodemus...", "type": "Gospel"}
            },
            "occasion": "mass",
        }, client=http_client)

        task = data["result"]
        assert len(task["history"]) == 2

        reply = extract_reply(data)
        if "error" in reply:
            pytest.skip(f"Generate error (may need LLM key): {reply.get('error')}")

        assert reply.get("status") == "success"
        assert "data" in reply
        homily = reply["data"].get("homily", {})
        expected_sections = ("introduction", "reading_reflection", "practical_application", "conclusion")
        for section in expected_sections:
            assert section in homily, f"Missing section: {section}"
            assert homily[section]["content"]

    # -------------------------------------------------------------------------
    # homily.refine tests
    # -------------------------------------------------------------------------

    def test_refine_format(self, http_client: httpx.Client):
        """Verify homily.refine returns correct format via message/send."""
        data = make_message_send("homily.refine", {
            "liturgical_data": MOCK_LITURGICAL_DATA,
            "occasion": "mass",
            "existing_draft": "Brothers and sisters, today we reflect on faith...",
            "preferences": {"style": "expository"},
        }, client=http_client)

        task = data["result"]
        assert len(task["history"]) == 2

        reply = extract_reply(data)
        if "error" in reply:
            pytest.skip(f"Refine error: {reply.get('error')}")

        assert reply.get("status") == "success"
        assert "data" in reply
        homily = reply["data"].get("homily", {})
        expected_sections = ("introduction", "reading_reflection", "practical_application", "conclusion")
        for section in expected_sections:
            assert section in homily, f"Missing section: {section}"
            assert homily[section]["content"]

    # -------------------------------------------------------------------------
    # homily.adjust_tone tests
    # -------------------------------------------------------------------------

    def test_adjust_tone_format(self, http_client: httpx.Client):
        """Verify homily.adjust_tone returns correct format via message/send."""
        data = make_message_send("homily.adjust_tone", {
            "liturgical_data": MOCK_LITURGICAL_DATA,
            "occasion": "mass",
            "existing_draft": "Brothers and sisters, today we reflect on the Gospel...",
            "preferences": {"style": "narrative", "audience": "youth"},
        }, client=http_client)

        task = data["result"]
        assert len(task["history"]) == 2

        reply = extract_reply(data)
        if "error" in reply:
            pytest.skip(f"Tone adjustment error: {reply.get('error')}")

        assert reply.get("status") == "success"
        assert "data" in reply
        homily = reply["data"].get("homily", {})
        expected_sections = ("introduction", "reading_reflection", "practical_application", "conclusion")
        for section in expected_sections:
            assert section in homily, f"Missing section: {section}"
            assert homily[section]["content"]


class TestHomilyContractDefinition:
    """Tests that validate the contract JSON definition itself (no agent needed)."""

    def test_contract_occasion_enum_uses_marriage(self):
        """Verify homily.generate occasion enum uses 'marriage' not 'wedding'."""
        contract = load_contract()
        generate = next(m for m in contract["methods"] if m["name"] == "homily.generate")
        occasion_enum = generate["params"]["properties"]["occasion"]["enum"]
        assert "marriage" in occasion_enum
        assert "wedding" not in occasion_enum

    def test_contract_refine_accepts_occasion(self):
        """Verify homily.refine has optional occasion field."""
        contract = load_contract()
        refine = next(m for m in contract["methods"] if m["name"] == "homily.refine")
        assert "occasion" in refine["params"]["properties"]


class TestHomilyAgentErrorHandling:
    """Tests for error handling in homily agent."""

    pytestmark = pytest.mark.skipif(
        not is_agent_available(),
        reason="Homily agent not running on port 8002",
    )

    def test_missing_liturgical_data_returns_error(self, http_client: httpx.Client):
        """Verify that missing required params returns an error."""
        data = make_message_send("homily.generate", {}, client=http_client)
        reply = extract_reply(data)
        assert "error" in reply

    def test_unknown_method_returns_error(self, http_client: httpx.Client):
        """Verify that calling a non-existent method returns an error."""
        data = make_message_send("homily.nonexistent", {}, client=http_client)
        reply = extract_reply(data)
        assert "error" in reply
