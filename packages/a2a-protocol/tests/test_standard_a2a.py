import json
import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from a2a_protocol.server import A2AServer, create_server


@pytest.fixture
def contract_path(tmp_path):
    """Create a temporary contract JSON file."""
    contract = {
        "name": "test-agent",
        "version": "0.1.0",
        "description": "A test agent",
        "transport": {"type": "http", "port": 8001, "endpoint": "/"},
        "protocol": {"type": "jsonrpc", "version": "2.0"},
        "methods": [
            {"name": "test.skill", "description": "A test skill"},
        ],
        "error_codes": {"-32601": "Method not found"},
    }
    path = tmp_path / "contract.json"
    path.write_text(json.dumps(contract))
    return str(path)


@pytest.fixture
def server(contract_path):
    """Create a server with a mock handler and valid contract."""
    async def handler(method, params):
        if method == "test.skill":
            return {"status": "success", "data": {"key": "value"}}
        raise ValueError(f"Unknown method: {method}")

    return create_server(
        handler=handler,
        name="test_agent",
        contract_path=contract_path,
        agent_url="http://test-agent:8001"
    )


class TestGenerateAgentCard:
    def test_has_required_fields(self, server):
        card = server._generate_agent_card()
        assert card["name"] == "test-agent"
        assert card["version"] == "0.1.0"
        assert card["url"] == "http://test-agent:8001"
        assert "capabilities" in card
        assert "defaultInputModes" in card
        assert "defaultOutputModes" in card
        assert "skills" in card
        assert "supportedInterfaces" in card

    def test_skills_listed(self, server):
        card = server._generate_agent_card()
        skill_names = [s["name"] for s in card["skills"]]
        assert "test.skill" in skill_names

    def test_agent_ping_not_in_skills(self, server):
        card = server._generate_agent_card()
        skill_names = [s["name"] for s in card["skills"]]
        assert "agent.ping" not in skill_names


class TestExtractTextFromMessage:
    def test_extracts_plain_string(self, server):
        msg = {"parts": [{"text": "hello world"}]}
        assert server._extract_text_from_message(msg) == "hello world"

    def test_handles_empty_parts(self, server):
        assert server._extract_text_from_message({"parts": []}) == ""

    def test_handles_no_parts_key(self, server):
        assert server._extract_text_from_message({}) == ""

    def test_extracts_from_first_part_only(self, server):
        msg = {"parts": [{"text": "first"}, {"text": "second"}]}
        assert server._extract_text_from_message(msg) == "first"

    def test_handles_text_as_non_string(self, server):
        msg = {"parts": [{"text": 12345}]}
        assert server._extract_text_from_message(msg) == "12345"


class TestDispatchFromText:
    def test_parses_json_method_call(self, server):
        result = server._dispatch_from_text('{"method":"test.skill","params":{"k":"v"}}')
        assert result == {"method": "test.skill", "params": {"k": "v"}}

    def test_plain_text_has_empty_method(self, server):
        result = server._dispatch_from_text("ciao")
        assert result["method"] == ""
        assert result["params"] == {"text": "ciao"}

    def test_dotted_method_without_params(self, server):
        result = server._dispatch_from_text("test.skill")
        assert result == {"method": "test.skill", "params": {}}

    def test_dotted_method_with_text_params(self, server):
        result = server._dispatch_from_text("test.skill some text here")
        assert result["method"] == "test.skill"
        assert result["params"] == {"text": "some text here"}

    def test_invalid_json_treated_as_plain_text(self, server):
        result = server._dispatch_from_text("{not valid json")
        assert result["method"] == ""
        assert result["params"] == {"text": "{not valid json"}


@pytest.mark.asyncio
class TestHandleSendMessage:
    async def test_state_is_lowercase_completed(self, server):
        body = {
            "id": "task-1",
            "message": {
                "id": "msg-1",
                "role": "user",
                "parts": [{"text": '{"method":"test.skill","params":{}}'}]
            }
        }
        result = await server._handle_send_message(body)
        assert result["status"]["state"] == "completed"
        assert result["id"] == "task-1"
        assert "contextId" in result

    async def test_parts_are_plain_strings(self, server):
        body = {
            "id": "task-2",
            "message": {
                "id": "msg-2",
                "role": "user",
                "parts": [{"text": "hello"}]
            }
        }
        result = await server._handle_send_message(body)
        for msg in result["history"]:
            for part in msg["parts"]:
                assert isinstance(part["text"], str), f"Expected str, got {type(part['text'])}"

    async def test_user_message_preserved_in_history(self, server):
        body = {
            "id": "task-3",
            "message": {
                "id": "msg-3",
                "role": "user",
                "parts": [{"text": "hello from user"}]
            }
        }
        result = await server._handle_send_message(body)
        history = result["history"]
        assert len(history) == 2
        assert history[0]["role"] == "user"
        assert history[0]["parts"][0]["text"] == "hello from user"
        assert history[1]["role"] == "agent"

    async def test_every_message_has_messageId(self, server):
        body = {
            "id": "task-4",
            "message": {
                "id": "msg-4",
                "role": "user",
                "parts": [{"text": "test"}]
            }
        }
        result = await server._handle_send_message(body)
        for msg in result["history"]:
            assert "messageId" in msg, f"Missing messageId in {msg}"
            assert isinstance(msg["messageId"], str)

    async def test_agent_ping_via_text_dispatch(self, server):
        body = {
            "id": "task-ping",
            "message": {
                "id": "msg-ping",
                "role": "user",
                "parts": [{"text": '{"method":"agent.ping","params":{}}'}]
            }
        }
        result = await server._handle_send_message(body)
        agent_reply = result["history"][1]["parts"][0]["text"]
        parsed = json.loads(agent_reply)
        assert parsed["status"] == "pong"
        assert parsed["agent"] == "test_agent"

    async def test_unknown_method_is_error(self, server):
        body = {
            "id": "task-err",
            "message": {
                "id": "msg-err",
                "role": "user",
                "parts": [{"text": "not a method call at all"}]
            }
        }
        result = await server._handle_send_message(body)
        agent_reply = result["history"][1]["parts"][0]["text"]
        parsed = json.loads(agent_reply)
        assert "error" in parsed


class TestHandleGetTask:
    def test_returns_task_with_required_fields(self, server):
        server._tasks["task-x"] = {
            "id": "task-x",
            "contextId": "ctx-x",
            "status": {"state": "completed"},
            "history": [
                {"messageId": "m1", "role": "user", "parts": [{"text": "hi"}]},
                {"messageId": "m2", "role": "agent", "parts": [{"text": "hello"}]},
            ],
        }
        result = server._handle_get_task("task-x")
        assert result["id"] == "task-x"
        assert result["contextId"] == "ctx-x"
        assert result["status"]["state"] == "completed"
        assert len(result["history"]) == 2

    def test_returns_error_for_unknown_task(self, server):
        result = server._handle_get_task("nonexistent")
        assert "error" in result
        assert result["error"]["code"] == -32602

    def test_state_is_lowercase_in_fallback(self, server):
        server._tasks["task-old"] = {
            "id": "task-old",
            "contextId": "ctx-old",
            "history": [
                {"messageId": "m1", "role": "user", "parts": [{"text": "hi"}]},
            ],
        }
        result = server._handle_get_task("task-old")
        assert result["status"]["state"] == "unknown"

    def test_empty_list_tasks(self, server):
        server._tasks = {}
        result = server._handle_list_tasks()
        assert result["tasks"] == []

    def test_list_tasks_summaries(self, server):
        server._tasks = {
            "t1": {"id": "t1", "status": {"state": "completed"}},
            "t2": {"id": "t2", "status": {"state": "working"}},
        }
        result = server._handle_list_tasks()
        assert len(result["tasks"]) == 2
