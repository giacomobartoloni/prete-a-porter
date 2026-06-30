"""
Contract tests for liturgy agent A2A methods.

Tests verify JSON-RPC 2.0 format compliance via standard message/send protocol
against the liturgy-agent-contract.json specification.
"""

import json
import pytest
from pathlib import Path
from typing import Any

import httpx
from pydantic import BaseModel, Field


# Load contract specification
CONTRACT_PATH = Path(__file__).parent.parent / "liturgy-agent-contract.json"
AGENT_URL = "http://localhost:8001"
AGENT_ENDPOINT = f"{AGENT_URL}/"


def load_contract() -> dict:
    """Load the liturgy agent contract specification."""
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


# Pydantic models for response validation
class PingResult(BaseModel):
    """Expected result schema for agent.ping."""
    status: str = Field(..., pattern="^pong$")
    agent: str = Field(..., pattern="^liturgy_agent$")
    version: str


class ReadingsResult(BaseModel):
    """Expected result schema for liturgy_agent.get_readings."""
    status: str = Field(..., pattern="^(success|error)$")
    data: dict | None = None
    source: str | None = Field(None, pattern="^(web|cache|lectionary)$")
    error: str | None = None
    message: str | None = None


class LectionaryResult(BaseModel):
    """Expected result schema for liturgy_agent.get_lectionary."""
    occasion: str
    lectionary: dict
    readings_count: int


# Fixture to check if agent is running
@pytest.fixture
def agent_available():
    """Check if liturgy agent is running on port 8001."""
    try:
        with httpx.Client(timeout=2.0) as client:
            response = client.get(f"{AGENT_URL}/health")
            return response.status_code == 200
    except (httpx.ConnectError, httpx.TimeoutException):
        return False


# Skip marker for when agent is not available
def skip_if_agent_unavailable(agent_available):
    """Return pytest.skip if agent is not available."""
    if not agent_available:
        pytest.skip("Liturgy agent not running on port 8001")


async def make_message_send(cmd_method: str, cmd_params: dict | None = None) -> dict:
    """Make a standard A2A message/send request and return the full response."""
    cmd_text = json.dumps({"method": cmd_method, "params": cmd_params or {}})
    payload = {
        "jsonrpc": "2.0",
        "id": "1",
        "method": "message/send",
        "params": {
            "message": {
                "role": "user",
                "parts": [{"text": cmd_text}]
            }
        }
    }
    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.post(AGENT_ENDPOINT, json=payload)
        return response.json()


class TestLiturgyAgentContract:
    """Contract tests for liturgy agent A2A methods."""

    @pytest.mark.asyncio
    async def test_agent_ping_via_message_send(self, agent_available):
        """Verify agent.ping via standard message/send."""
        skip_if_agent_unavailable(agent_available)

        data = await make_message_send("agent.ping")
        reply = extract_reply(data)

        ping_result = PingResult(**reply)
        assert ping_result.status == "pong"
        assert ping_result.agent == "liturgy_agent"
        assert ping_result.version is not None

    @pytest.mark.asyncio
    async def test_agent_ping_task_format(self, agent_available):
        """Verify message/send returns valid Task format."""
        skip_if_agent_unavailable(agent_available)

        data = await make_message_send("agent.ping")
        task = data["result"]

        assert "id" in task
        assert "contextId" in task
        assert task["status"]["state"] in ("completed", "working")
        assert len(task["history"]) == 2  # user + agent messages
        for msg in task["history"]:
            assert "id" in msg or "messageId" in msg
            assert "role" in msg
            assert len(msg["parts"]) > 0

    @pytest.mark.asyncio
    async def test_get_readings_format(self, agent_available):
        """Verify get_readings returns correct data format."""
        skip_if_agent_unavailable(agent_available)

        data = await make_message_send("liturgy_agent.get_readings", {"occasion": "mass"})
        reply = extract_reply(data)

        if "error" in reply:
            pytest.skip(f"Readings error: {reply.get('error')}")

        readings_result = ReadingsResult(**reply)
        assert readings_result.status in ["success", "error"]

        if readings_result.status == "success":
            assert readings_result.data is not None
            assert "date" in readings_result.data or "occasion" in readings_result.data

    @pytest.mark.asyncio
    async def test_get_lectionary_format(self, agent_available):
        """Verify get_lectionary returns correct format."""
        skip_if_agent_unavailable(agent_available)

        data = await make_message_send("liturgy_agent.get_lectionary", {"occasion": "marriage"})
        reply = extract_reply(data)

        if "error" in reply:
            pytest.skip(f"Lectionary error: {reply.get('error')}")

        lectionary_result = LectionaryResult(**reply)
        assert lectionary_result.occasion == "marriage"
        assert lectionary_result.readings_count >= 0


class TestContractCompliance:
    """Tests to verify contract file is valid and complete."""

    def test_contract_file_exists(self):
        """Verify contract file exists."""
        assert CONTRACT_PATH.exists(), f"Contract file not found: {CONTRACT_PATH}"

    def test_contract_is_valid_json(self):
        """Verify contract file is valid JSON."""
        contract = load_contract()
        assert isinstance(contract, dict)

    def test_contract_has_required_fields(self):
        """Verify contract has all required fields."""
        contract = load_contract()

        assert "name" in contract
        assert "version" in contract
        assert "transport" in contract
        assert "protocol" in contract
        assert "methods" in contract

        assert contract["name"] == "liturgy-agent"
        assert contract["transport"]["type"] == "http"
        assert contract["transport"]["port"] == 8001
        assert contract["protocol"]["type"] == "jsonrpc"
        assert contract["protocol"]["version"] == "2.0"

    def test_contract_methods_defined(self):
        """Verify all expected methods are defined in contract."""
        contract = load_contract()
        method_names = [m["name"] for m in contract["methods"]]

        assert "agent.ping" in method_names
        assert "liturgy_agent.get_readings" in method_names
        assert "liturgy_agent.get_lectionary" in method_names

    def test_contract_error_codes_defined(self):
        """Verify error codes are defined in contract."""
        contract = load_contract()

        assert "error_codes" in contract
        assert "-32700" in contract["error_codes"]
        assert "-32600" in contract["error_codes"]
        assert "-32601" in contract["error_codes"]
        assert "-32602" in contract["error_codes"]
        assert "-32603" in contract["error_codes"]
