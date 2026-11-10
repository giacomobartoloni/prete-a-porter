"""Observe message lifecycle at the Chainlit boundary, including interruptions."""

import pytest

from prete_chat import presentation


class Message:
    events = []

    def __init__(self, content="", metadata=None, actions=None):
        self.content = content
        self.metadata = metadata or {}
        self.actions = actions or []

    async def send(self):
        self.events.append(("send", self.content, list(self.actions)))

    async def update(self):
        self.events.append(("update", self.content, list(self.actions)))

    async def remove(self):
        self.events.append(("remove", self.content))

    async def stream_token(self, text):
        self.content += text
        self.events.append(("stream", self.content, list(self.actions)))


@pytest.fixture
def view(monkeypatch):
    Message.events = []
    monkeypatch.setattr(presentation.cl, "Message", Message)
    return presentation.TurnPresentation()


async def test_progress_precedes_lazy_answer_and_actions_wait_for_completion(view):
    await view.start()
    assert Message.events == [("send", "Sto elaborando la richiesta…", [])]
    await view.tool_started("Recupero le letture liturgiche")
    assert Message.events[-1][1] == "Recupero le letture liturgiche…"
    await view.stream_token("Testo")
    assert Message.events[-2][0] == "remove"
    assert Message.events[-1] == ("stream", "Testo", [])
    await view.finish(actions=["refine"])
    assert Message.events[-1] == ("update", "Testo", ["refine"])
    assert view.answer.metadata["model_content"] == "Testo"


@pytest.mark.parametrize("partial", ["", "Testo parziale"])
async def test_error_or_cancel_keeps_notice_out_of_model_context(view, partial):
    await view.start()
    if partial:
        await view.stream_token(partial)
    await view.finish(notice="Operazione interrotta")
    assert "Operazione interrotta" in view.answer.content
    assert view.answer.metadata["model_content"] == partial
    assert not view.answer.actions
    assert all(event[1] for event in Message.events if event[0] == "send")


async def test_tool_end_shows_honest_wait_and_empty_completion_is_explicit(view):
    await view.start()
    await view.tool_finished()
    assert Message.events[-1][1] == "Preparo la risposta…"
    await view.finish()
    assert view.answer.content
    assert view.answer.metadata["model_content"] == ""


async def test_lazy_stream_keeps_a_timestamp_for_persistence_and_resume(view):
    await view.start()
    await view.stream_token("Prima")
    timestamp = getattr(view.answer, "created_at", None)
    assert timestamp
    await view.stream_token(" seconda")
    await view.finish()
    assert view.answer.created_at == timestamp


async def test_whitespace_only_stream_is_an_explicit_empty_result(view):
    await view.start()
    await view.stream_token(" \n ")
    assert view.answer is None
    await view.finish(actions=["refine"])
    assert view.answer.content == presentation.EMPTY_RESPONSE_NOTICE
    assert view.answer.metadata["model_content"] == ""
    assert view.answer.actions == []


async def test_initial_whitespace_is_preserved_when_actual_text_arrives(view):
    await view.start()
    await view.stream_token(" ")
    await view.stream_token("testo")
    await view.finish()
    assert view.answer.content == " testo"
    assert view.answer.metadata["model_content"] == " testo"
