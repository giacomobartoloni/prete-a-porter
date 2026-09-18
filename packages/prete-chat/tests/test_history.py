"""Model-visible history: accumulation and message building (plan §15)."""

from prete_chat import history


class TestAppend:
    def test_appends_user_and_assistant_turns_in_order(self):
        turns: list[dict[str, str]] = []
        history.append(turns, "user", "ciao")
        history.append(turns, "assistant", "salve")
        assert turns == [
            {"role": "user", "content": "ciao"},
            {"role": "assistant", "content": "salve"},
        ]

    def test_ignores_whitespace_only_content(self):
        """A failed turn with no model text must not become an empty assistant turn."""
        turns: list[dict[str, str]] = []
        history.append(turns, "assistant", "   \n")
        assert turns == []

    def test_strips_surrounding_whitespace(self):
        turns: list[dict[str, str]] = []
        history.append(turns, "assistant", "  salve  ")
        assert turns[0]["content"] == "salve"


class TestBuildMessages:
    def test_appends_the_new_user_turn_after_the_history(self):
        turns = [
            {"role": "user", "content": "prima domanda"},
            {"role": "assistant", "content": "prima risposta"},
        ]
        messages = history.build_messages(turns, "seconda domanda")
        assert [m.role for m in messages] == ["user", "assistant", "user"]
        assert messages[-1].content == "seconda domanda"

    def test_empty_history_holds_only_the_new_turn(self):
        messages = history.build_messages([], "prima domanda")
        assert len(messages) == 1
        assert messages[0].role == "user"
        assert messages[0].content == "prima domanda"
