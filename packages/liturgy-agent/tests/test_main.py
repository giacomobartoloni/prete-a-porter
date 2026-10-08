import pytest
from unittest.mock import patch, MagicMock


@pytest.mark.asyncio
async def test_unknown_occasion_advertises_daily(monkeypatch, tmp_path):
    from liturgy_agent.main import LiturgyAgentHandler

    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "liturgy.db"))
    handler = LiturgyAgentHandler.__new__(LiturgyAgentHandler)
    handler.llm = None
    with pytest.raises(ValueError) as error:
        await handler._handle_get_readings({"occasion": "invalid"})
    valid_options = str(error.value).split("Valid options: ")[1].split(", ")
    assert "daily" in valid_options


class TestHandleGetLectionary:
    """Tests for LiturgyAgentHandler._handle_get_lectionary."""

    @patch("liturgy_agent.agent.LiturgyAgent")
    def test_raises_value_error_when_lectionary_none(self, mock_agent_class):
        from liturgy_agent.main import LiturgyAgentHandler

        mock_agent = MagicMock()
        mock_agent._load_lectionary.return_value = None
        mock_agent_class.return_value = mock_agent

        handler = LiturgyAgentHandler()
        handler.llm = MagicMock()

        with pytest.raises(ValueError, match="No lectionary data found for occasion: marriage"):
            import asyncio
            asyncio.run(handler._handle_get_lectionary({"occasion": "marriage"}))

    @patch("liturgy_agent.agent.LiturgyAgent")
    def test_raises_value_error_when_missing_occasion(self, mock_agent_class):
        from liturgy_agent.main import LiturgyAgentHandler

        handler = LiturgyAgentHandler()
        handler.llm = MagicMock()

        with pytest.raises(ValueError, match="Missing required parameter: occasion"):
            import asyncio
            asyncio.run(handler._handle_get_lectionary({}))
