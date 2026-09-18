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


class TestFromThread:
    """Resume reconstruction from a Chainlit ThreadDict (plan §15)."""

    _THREAD = {
        "id": "thread-1",
        "steps": [
            {"type": "run", "name": "agent", "createdAt": "2026-09-18T10:00:00Z", "output": "{...}"},
            {"type": "user_message", "output": "Quali sono le letture?", "createdAt": "2026-09-18T10:00:01Z"},
            {"type": "tool", "name": "Recupero le letture liturgiche", "createdAt": "2026-09-18T10:00:02Z", "output": "{}"},
            {"type": "assistant_message", "output": "Ecco le letture.", "createdAt": "2026-09-18T10:00:03Z"},
            {"type": "llm", "name": "agent", "createdAt": "2026-09-18T10:00:04Z", "output": "..."},
            {"type": "user_message", "output": "Grazie", "createdAt": "2026-09-18T10:00:05Z"},
            {"type": "assistant_message", "output": "Prego", "createdAt": "2026-09-18T10:00:06Z"},
        ],
    }

    def test_keeps_only_user_and_assistant_messages_in_order(self):
        assert history.from_thread(self._THREAD) == [
            {"role": "user", "content": "Quali sono le letture?"},
            {"role": "assistant", "content": "Ecco le letture."},
            {"role": "user", "content": "Grazie"},
            {"role": "assistant", "content": "Prego"},
        ]

    def test_orders_by_created_at_not_input_order(self):
        thread = {
            "steps": [
                {"type": "assistant_message", "output": "seconda", "createdAt": "2026-09-18T10:00:02Z"},
                {"type": "user_message", "output": "prima", "createdAt": "2026-09-18T10:00:01Z"},
            ]
        }
        assert [turn["content"] for turn in history.from_thread(thread)] == ["prima", "seconda"]

    def test_missing_steps_yield_an_empty_history(self):
        assert history.from_thread({}) == []

    def test_blank_messages_are_skipped(self):
        thread = {"steps": [{"type": "assistant_message", "output": "   ", "createdAt": "x"}]}
        assert history.from_thread(thread) == []

    def test_non_string_outputs_are_skipped(self):
        thread = {"steps": [{"type": "user_message", "output": None, "createdAt": "x"}]}
        assert history.from_thread(thread) == []

    def test_welcome_message_is_not_a_model_turn(self):
        thread = {
            "steps": [
                {
                    "type": "assistant_message",
                    "output": "Benvenuto!",
                    "createdAt": "2026-09-18T09:59:59Z",
                    "metadata": {history.WELCOME_METADATA_KEY: True},
                },
                {"type": "user_message", "output": "Ciao", "createdAt": "2026-09-18T10:00:00Z"},
            ]
        }
        assert history.from_thread(thread) == [{"role": "user", "content": "Ciao"}]


# Captured from a real ThreadDict on 2026-09-18 (Chainlit 2.12.0 + the
# PostgreSQL data layer), trimmed but field-for-field: this pins the
# reconstruction to the shape the framework actually passes to
# `@cl.on_chat_resume`, including the welcome flag, tool/llm noise steps and
# the ISO `createdAt` strings the data layer returns.
REAL_THREAD = {
    "id": "530d8ff5-e182-4e0e-9e4a-6d260b6e58a0",
    "name": "Che letture ci sono per un matrimonio?",
    "metadata": {"chat_profile": None},
    "userIdentifier": "secondo@prete-a-porter.dev",
    "steps": [
        {
            "id": "b0b4e1f8-0000-0000-0000-000000000000",
            "name": "on_chat_start",
            "type": "run",
            "output": "",
            "createdAt": "2026-09-18T16:37:20.611294Z",
            "metadata": {},
        },
        {
            "id": "47c2ebfd-5085-4dfe-add1-16a0d2e6eb20",
            "name": "Prête-à-Porter",
            "type": "assistant_message",
            "output": "Benvenuto. Posso cercare le letture liturgiche e preparare un'omelia.",
            "createdAt": "2026-09-18T16:37:20.613852Z",
            "metadata": {"welcome": True},
        },
        {
            "id": "15e46919-db62-4093-8922-1dbd81c9329b",
            "name": "secondo@prete-a-porter.dev",
            "type": "user_message",
            "output": "Che letture ci sono per un matrimonio?",
            "createdAt": "2026-09-18T16:37:22.885450Z",
            "metadata": {"location": "http://localhost:3003/"},
        },
        {
            "id": "9c0e0a5c-0000-0000-0000-000000000000",
            "name": "LangGraph",
            "type": "run",
            "output": "{}",
            "createdAt": "2026-09-18T16:37:22.908304Z",
            "metadata": {},
        },
        {
            "id": "3f21f8b4-0000-0000-0000-000000000000",
            "name": "Cerco le opzioni del lezionario",
            "type": "tool",
            "output": '{"status": "success"}',
            "createdAt": "2026-09-18T16:37:24.283109Z",
            "metadata": {},
        },
        {
            "id": "6d0c9f1e-0000-0000-0000-000000000000",
            "name": "Prête-à-Porter",
            "type": "assistant_message",
            "output": "Il Lezionario prevede un numero più ampio di opzioni.",
            "createdAt": "2026-09-18T16:37:24.307751Z",
            "metadata": {},
        },
    ],
}


class TestRealThreadFixture:
    def test_reconstruction_matches_the_framework_shape(self):
        assert history.from_thread(REAL_THREAD) == [
            {"role": "user", "content": "Che letture ci sono per un matrimonio?"},
            {"role": "assistant", "content": "Il Lezionario prevede un numero più ampio di opzioni."},
        ]
