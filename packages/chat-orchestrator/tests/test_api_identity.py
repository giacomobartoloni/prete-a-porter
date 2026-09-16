"""Per-user identity and thread correlation from OpenWebUI headers."""

import uuid

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from chat_orchestrator.api.identity import CallerIdentity, get_caller_identity


@pytest.fixture
def client():
    app = FastAPI()

    @app.get("/whoami")
    async def whoami(identity: CallerIdentity = Depends(get_caller_identity)) -> dict:
        return {
            "user_id": identity.user_id,
            "thread_id": identity.thread_id,
            "user_email": identity.user_email,
        }

    return TestClient(app)


class TestForwardedHeaders:
    def test_reads_user_and_chat_id(self, client):
        body = client.get(
            "/whoami",
            headers={
                "X-OpenWebUI-User-Id": "user-42",
                "X-OpenWebUI-Chat-Id": "chat-99",
                "X-OpenWebUI-User-Email": "don@example.com",
            },
        ).json()
        assert body["user_id"] == "user-42"
        assert body["thread_id"] == "chat-99"
        assert body["user_email"] == "don@example.com"

    def test_header_names_are_case_insensitive(self, client):
        body = client.get("/whoami", headers={"x-openwebui-user-id": "user-7"}).json()
        assert body["user_id"] == "user-7"


class TestFallbacks:
    def test_missing_user_id_falls_back_to_anonymous(self, client):
        body = client.get("/whoami").json()
        assert body["user_id"] == "anonymous"

    def test_missing_chat_id_generates_a_uuid(self, client):
        body = client.get("/whoami").json()
        uuid.UUID(body["thread_id"])  # raises if not a valid UUID

    def test_generated_thread_ids_differ_per_request(self, client):
        first = client.get("/whoami").json()["thread_id"]
        second = client.get("/whoami").json()["thread_id"]
        assert first != second

    def test_missing_email_is_none(self, client):
        assert client.get("/whoami").json()["user_email"] is None

    def test_blank_user_id_falls_back_to_anonymous(self, client):
        """An empty header value must not become the identity."""
        body = client.get("/whoami", headers={"X-OpenWebUI-User-Id": ""}).json()
        assert body["user_id"] == "anonymous"

    def test_blank_chat_id_generates_a_uuid(self, client):
        body = client.get("/whoami", headers={"X-OpenWebUI-Chat-Id": ""}).json()
        uuid.UUID(body["thread_id"])


class TestDegradationIsWarned:
    def test_missing_user_id_logs_a_warning(self, client, caplog):
        import logging
        import chat_orchestrator.api.identity as identity_mod
        identity_mod._warned_missing_user_id = False
        with caplog.at_level(logging.WARNING):
            client.get("/whoami")
        assert any("X-OpenWebUI-User-Id" in record.message for record in caplog.records)

    def test_warning_is_emitted_only_once(self, client, caplog):
        import logging
        import chat_orchestrator.api.identity as identity_mod
        identity_mod._warned_missing_user_id = False
        with caplog.at_level(logging.WARNING):
            client.get("/whoami")
            caplog.clear()
            client.get("/whoami")
        assert not any("X-OpenWebUI-User-Id" in record.message for record in caplog.records)
