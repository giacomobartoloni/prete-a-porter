"""
Contract tests for liturgy agent A2A methods.

Tests verify JSON-RPC 2.0 format compliance via standard message/send protocol
against the liturgy-agent-contract.json specification.
"""

import json
import os
import pytest
from pathlib import Path
from typing import Any

import httpx
from pydantic import BaseModel, Field

from conftest import a2a_apost
from models import DailyMassResultContract, LectionaryRequestContract, LectionaryResultContract, PingRequestContract, PingResultContract, ReadingsErrorContract, ReadingsRequestContract, RitualReadingsResultContract, inline_schema


# Load contract specification
CONTRACT_PATH = Path(__file__).parent.parent / "liturgy-agent-contract.json"
AGENT_URL = os.environ.get("A2A_LITURGY_URL", "http://localhost:8001")
AGENT_ENDPOINT = f"{AGENT_URL.rstrip('/')}/"


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


def require_agent_available(agent_available):
    """Fail required live checks when the liturgy agent is unavailable."""
    if not agent_available:
        pytest.fail(f"Liturgy agent not running at {AGENT_URL}")


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
    response = await a2a_apost(AGENT_ENDPOINT, json=payload, timeout=15.0)
    return response.json()


class TestLiturgyAgentContract:
    """Contract tests for liturgy agent A2A methods."""

    @pytest.mark.asyncio
    async def test_agent_ping_via_message_send(self, agent_available):
        """Verify agent.ping via standard message/send."""
        require_agent_available(agent_available)

        data = await make_message_send("agent.ping")
        reply = extract_reply(data)

        ping_result = PingResult(**reply)
        assert ping_result.status == "pong"
        assert ping_result.agent == "liturgy_agent"
        assert ping_result.version is not None

    @pytest.mark.asyncio
    async def test_agent_ping_task_format(self, agent_available):
        """Verify message/send returns valid Task format."""
        require_agent_available(agent_available)

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
    @pytest.mark.optional_live
    async def test_get_readings_format(self, agent_available):
        """Verify get_readings returns correct data format (optional live upstream)."""
        from conftest import require_optional_live

        require_optional_live()
        require_agent_available(agent_available)

        data = await make_message_send("liturgy_agent.get_readings", {"occasion": "mass"})
        reply = extract_reply(data)

        if "error" in reply:
            pytest.fail(f"Readings error: {reply.get('error')}")

        readings_result = DailyMassResultContract.model_validate(reply)
        assert readings_result.status == "success"
        assert readings_result.data is not None
        assert readings_result.data.occasion == "mass"

    @pytest.mark.asyncio
    async def test_get_lectionary_format(self, agent_available):
        """Verify get_lectionary returns correct format."""
        require_agent_available(agent_available)

        data = await make_message_send("liturgy_agent.get_lectionary", {"occasion": "marriage"})
        reply = extract_reply(data)

        if "error" in reply:
            pytest.fail(f"Lectionary error: {reply.get('error')}")

        lectionary_result = LectionaryResultContract.model_validate(reply)
        assert lectionary_result.occasion == "marriage"
        assert lectionary_result.readings_count >= 0

    @pytest.mark.asyncio
    @pytest.mark.parametrize("occasion", ["marriage", "baptism", "funeral"])
    async def test_ritual_readings_consumer_shape(self, agent_available, occasion):
        require_agent_available(agent_available)
        reply = extract_reply(await make_message_send("liturgy_agent.get_readings", {"occasion": occasion}))
        result = RitualReadingsResultContract.model_validate(reply)
        assert set(result.data.root) == {occasion}

    @pytest.mark.asyncio
    @pytest.mark.parametrize("method,params", [
        ("liturgy_agent.unknown", {}),
        ("liturgy_agent.get_readings", {}),
        ("liturgy_agent.get_readings", {"occasion": "invalid"}),
        ("liturgy_agent.get_readings", {"occasion": "mass", "date": "invalid"}),
    ])
    async def test_custom_root_errors_are_sanitized(self, agent_available, method, params):
        require_agent_available(agent_available)
        response = await a2a_apost(AGENT_ENDPOINT, json={"jsonrpc": "2.0", "id": "invalid-input", "method": method, "params": params})
        assert response.status_code == 200
        body = response.json()
        assert body["id"] == "invalid-input"
        assert body["error"]["code"] == -32603
        assert body["error"]["message"] == "Internal error"
        assert set(body["error"]["data"]) == {"error_id"}
        assert body["error"]["data"]["error_id"]


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
        assert contract["transport"]["endpoint"] == "/"
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
        assert set(contract["error_codes"]) == {"-32603"}

    def test_daily_and_ritual_response_variants(self):
        # These assertions intentionally duplicate the consumer-visible contract.
        # Do not weaken to generic dict assertions; they are a drift guard.
        contract = load_contract()
        readings = next(m for m in contract["methods"] if m["name"] == "liturgy_agent.get_readings")
        assert "daily" in readings["params"]["properties"]["occasion"]["enum"]
        daily, ritual, error = readings["returns"]["oneOf"]
        fields = daily["properties"]["data"]["properties"]
        assert set(fields) == {"date", "occasion", "metadata", "first_reading", "psalm", "second_reading", "gospel", "alleluia_verse", "cached_at", "source"}
        assert ritual["properties"]["source"]["const"] == "lectionary"
        assert error["properties"]["status"]["const"] == "error"

    def test_lectionary_has_no_obsolete_bug(self):
        method = next(m for m in load_contract()["methods"] if m["name"] == "liturgy_agent.get_lectionary")
        assert "KNOWN BUG" not in json.dumps(method)
        assert "AttributeError" not in json.dumps(method)

    @pytest.mark.parametrize("name", ["agent.ping", "liturgy_agent.get_readings", "liturgy_agent.get_lectionary"])
    def test_schemas_and_examples_match_independent_consumers(self, name):
        contract = load_contract()
        assert set(contract["error_codes"]) == {"-32603"}
        method = next(m for m in contract["methods"] if m["name"] == name)
        if name != "agent.ping":
            assert len(method["errors"]) == 1
            assert method["errors"][0]["code"] == -32603
            assert method["errors"][0]["message"] == "Internal error"
            assert set(method["errors"][0]["data"]) == {"error_id"}
        request_model = {"agent.ping": PingRequestContract, "liturgy_agent.get_readings": ReadingsRequestContract, "liturgy_agent.get_lectionary": LectionaryRequestContract}[name]
        results = [DailyMassResultContract, RitualReadingsResultContract, ReadingsErrorContract] if name.endswith("get_readings") else [PingResultContract if name == "agent.ping" else LectionaryResultContract]
        assert method["params"] == inline_schema(request_model)
        expected = {"oneOf": [inline_schema(model) for model in results]} if len(results) > 1 else inline_schema(results[0])
        if name == "agent.ping":
            expected["properties"]["agent"] = {"type": "string", "const": "liturgy_agent"}
        assert method["returns"] == expected
        for label, example in method["examples"].items():
            if label.startswith("request"):
                assert example["method"] == name
                request_model.model_validate(example["params"])
            elif "result" in example:
                result = example["result"]
                model = ReadingsErrorContract if result.get("status") == "error" else RitualReadingsResultContract if result.get("source") == "lectionary" else results[0]
                model.model_validate(result)
            else:
                assert example["error"]["code"] == -32603
                assert example["error"]["message"] == "Internal error"
                assert example["error"]["data"]["error_id"]
