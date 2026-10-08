"""
Contract tests for Homily Agent A2A methods.

Tests verify that the homily agent complies with the standard A2A protocol
specification defined in contracts/homily-agent-contract.json.
Required generate/refine/adjust checks use local fixture data / TEST_MODE and
fail when the agent is unavailable (not optional_live).
"""

import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, Optional

import httpx
import pytest

from conftest import MOCK_LITURGICAL_DATA, a2a_auth_headers
from models import GenerateRequestContract, HomilySuccessContract, PingRequestContract, PingResultContract, RefineRequestContract, inline_schema


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


def require_homily_agent() -> None:
    """Fail required live checks when the homily agent is unavailable."""
    if not is_agent_available():
        pytest.fail(f"Homily agent not running at {HOMILY_AGENT_URL}")


@pytest.fixture
def contract() -> Dict[str, Any]:
    """Load the contract specification."""
    return load_contract()


@pytest.fixture
def http_client() -> httpx.Client:
    """Create an HTTP client for A2A requests."""
    return httpx.Client(timeout=120.0, headers=a2a_auth_headers())


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
    with_cls = client or httpx.Client(timeout=120.0, headers=a2a_auth_headers())
    try:
        response = with_cls.post(f"{HOMILY_AGENT_URL}/", json=payload)
        response.raise_for_status()
        return response.json()
    finally:
        if client is None:
            with_cls.close()


class TestHomilyAgentContract:
    """Contract tests for homily agent A2A methods."""

    # -------------------------------------------------------------------------
    # agent.ping tests (required when the agent is under test)
    # -------------------------------------------------------------------------

    def test_agent_ping_format(self, http_client: httpx.Client):
        """Verify agent.ping via standard message/send."""
        require_homily_agent()
        data = make_message_send("agent.ping", client=http_client)
        reply = extract_reply(data)

        assert "status" in reply
        assert reply["status"] in ["ok", "pong"]
        assert reply.get("agent") == "homily_agent"

    def test_agent_ping_task_structure(self, http_client: httpx.Client):
        """Verify message/send returns valid Task structure."""
        require_homily_agent()
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
    # homily.generate / refine / tone — mandatory with local fixture / TEST_MODE
    # -------------------------------------------------------------------------

    def test_generate_format(self, http_client: httpx.Client):
        """Verify homily.generate returns correct format via message/send."""
        require_homily_agent()
        data = make_message_send("homily.generate", {
            "liturgical_data": MOCK_LITURGICAL_DATA,
            "occasion": "mass",
            "preferences": {"target_audience": "youth", "tone": "conversational", "length": "short"},
        }, client=http_client)

        task = data["result"]
        assert len(task["history"]) == 2

        reply = extract_reply(data)
        if "error" in reply:
            pytest.fail(f"Generate error: {reply.get('error')}")

        result = HomilySuccessContract.model_validate(reply)
        assert result.data.homily.occasion == "mass"
        assert result.data.homily.liturgical_date == MOCK_LITURGICAL_DATA["date"]

    def test_refine_format(self, http_client: httpx.Client):
        """Verify homily.refine returns correct format via message/send."""
        require_homily_agent()
        data = make_message_send("homily.refine", {
            "liturgical_data": MOCK_LITURGICAL_DATA,
            "occasion": "mass",
            "existing_draft": "Brothers and sisters, today we reflect on faith...",
            "preferences": {"tone": "formal"},
        }, client=http_client)

        task = data["result"]
        assert len(task["history"]) == 2

        reply = extract_reply(data)
        if "error" in reply:
            pytest.fail(f"Refine error: {reply.get('error')}")

        result = HomilySuccessContract.model_validate(reply)
        assert result.data.homily.occasion == "mass"
        assert result.data.homily.liturgical_date == MOCK_LITURGICAL_DATA["date"]

    def test_adjust_tone_format(self, http_client: httpx.Client):
        """Verify homily.adjust_tone returns correct format via message/send."""
        require_homily_agent()
        data = make_message_send("homily.adjust_tone", {
            "liturgical_data": MOCK_LITURGICAL_DATA,
            "occasion": "mass",
            "existing_draft": "Brothers and sisters, today we reflect on the Gospel...",
            "preferences": {"tone": "conversational", "target_audience": "youth", "length": "short"},
        }, client=http_client)

        task = data["result"]
        assert len(task["history"]) == 2

        reply = extract_reply(data)
        if "error" in reply:
            pytest.fail(f"Tone adjustment error: {reply.get('error')}")

        result = HomilySuccessContract.model_validate(reply)
        assert result.data.homily.occasion == "mass"
        assert result.data.homily.liturgical_date == MOCK_LITURGICAL_DATA["date"]


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

    @pytest.mark.parametrize("name", ["homily.generate", "homily.refine", "homily.adjust_tone"])
    def test_consumer_visible_shapes(self, name):
        # These assertions intentionally duplicate the consumer-visible contract.
        # Do not weaken to generic dict assertions; they are a drift guard.
        contract = load_contract()
        assert contract["transport"]["endpoint"] == "/"
        method = next(m for m in contract["methods"] if m["name"] == name)
        preferences = method["params"]["properties"]["preferences"]["properties"]
        assert set(preferences) == {"target_audience", "tone", "length", "themes", "metaphors", "analogies", "parables"}
        required = set(method["params"]["required"])
        assert "liturgical_data" in required
        if name != "homily.generate":
            assert "existing_draft" in required
        data = method["returns"]["properties"]["data"]["properties"]
        assert set(data["homily"]["properties"]) == {"introduction", "reading_reflection", "practical_application", "conclusion", "occasion", "liturgical_date"}
        assert data["sources"]["items"]["type"] == "string"

    @pytest.mark.parametrize("name", ["agent.ping", "homily.generate", "homily.refine", "homily.adjust_tone"])
    def test_schemas_and_examples_match_independent_consumers(self, name):
        method = next(m for m in load_contract()["methods"] if m["name"] == name)
        request_model = PingRequestContract if name == "agent.ping" else GenerateRequestContract if name == "homily.generate" else RefineRequestContract
        result_model = PingResultContract if name == "agent.ping" else HomilySuccessContract
        assert method["params"] == inline_schema(request_model)
        expected = inline_schema(result_model)
        if name == "agent.ping":
            expected["properties"]["agent"] = {"type": "string", "const": "homily_agent"}
        assert method["returns"] == expected
        for label, example in method["examples"].items():
            if label.startswith("request"):
                assert example["method"] == name
                request_model.model_validate(example["params"])
            elif "result" in example:
                result_model.model_validate(example["result"])
            else:
                assert example["error"]["code"] == -32603
                assert example["error"]["message"] == "Internal error"
                assert example["error"]["data"]["error_id"]


class TestHomilyAgentErrorHandling:
    """Tests for error handling in homily agent."""

    def test_missing_liturgical_data_returns_error(self, http_client: httpx.Client):
        """Verify that missing required params returns an error."""
        require_homily_agent()
        data = make_message_send("homily.generate", {}, client=http_client)
        reply = extract_reply(data)
        assert "error" in reply

    def test_unknown_method_returns_error(self, http_client: httpx.Client):
        """Verify that calling a non-existent method returns an error."""
        require_homily_agent()
        data = make_message_send("homily.nonexistent", {}, client=http_client)
        reply = extract_reply(data)
        assert "error" in reply

    @pytest.mark.parametrize("method,params", [
        ("homily.unknown", {}),
        ("homily.generate", {}),
        ("homily.refine", {"liturgical_data": MOCK_LITURGICAL_DATA}),
        ("homily.adjust_tone", {"liturgical_data": MOCK_LITURGICAL_DATA}),
    ])
    def test_custom_root_errors_are_sanitized(self, http_client, method, params):
        require_homily_agent()
        response = http_client.post(HOMILY_AGENT_URL.rstrip("/") + load_contract()["transport"]["endpoint"], json={"jsonrpc": "2.0", "id": "invalid-input", "method": method, "params": params})
        assert response.status_code == 200
        body = response.json()
        assert body["id"] == "invalid-input"
        assert body["error"]["code"] == -32603
        assert body["error"]["message"] == "Internal error"
        assert set(body["error"]["data"]) == {"error_id"}
        assert body["error"]["data"]["error_id"]
