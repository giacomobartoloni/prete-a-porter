"""Step labels: Italian titles for every tool the core can call."""

from chainlit.langchain.callbacks import LangchainCallbackHandler
from chat_orchestrator.graph import TOOLS_REGISTRY

from prete_chat import labels


class TestToolStepLabel:
    def test_known_tool_gets_its_italian_label(self):
        assert labels.tool_step_label("get_liturgical_readings") == "Recupero le letture liturgiche"

    def test_unknown_tool_keeps_its_name(self):
        assert labels.tool_step_label("some_future_tool") == "some_future_tool"

    def test_every_core_tool_has_a_label(self):
        """Drift guard: a tool added to the core without a label shows here."""
        unlabelled = [name for name in TOOLS_REGISTRY if labels.tool_step_label(name) == name]
        assert unlabelled == []


class TestItalianLabelsHandler:
    def test_is_accepted_wherever_the_stock_handler_is(self):
        """The app hands it to the core where Chainlit's handler is expected."""
        assert issubclass(labels.ItalianLabelsHandler, LangchainCallbackHandler)


async def test_progress_callbacks_do_not_replace_langchain_tool_hooks(monkeypatch):
    from types import SimpleNamespace

    from chainlit.langchain.callbacks import LangchainCallbackHandler

    monkeypatch.setattr(LangchainCallbackHandler, "__init__", lambda self: None)
    progress = []

    async def started(label):
        progress.append(label + "…")

    async def ended():
        progress.append("end")

    handler = labels.ItalianLabelsHandler(on_tool_start=started, on_tool_end=ended)
    # LangChain calls these inherited hooks with a Run object, not a label.
    await handler._on_tool_start(SimpleNamespace(name="get_liturgical_readings"))
    await handler._on_tool_end(SimpleNamespace(name="get_liturgical_readings"))
    assert progress == []


async def test_worker_trace_and_progress_run_on_ui_loop(monkeypatch):
    import asyncio
    from types import SimpleNamespace

    monkeypatch.setattr(LangchainCallbackHandler, "__init__", lambda self: None)
    owner = asyncio.get_running_loop()
    observed = []

    async def trace(self, run):
        observed.append(asyncio.get_running_loop())

    async def progress(label):
        observed.append(asyncio.get_running_loop())

    monkeypatch.setattr(LangchainCallbackHandler, "_start_trace", trace)
    monkeypatch.setattr(LangchainCallbackHandler, "_end_trace", trace)
    handler = labels.ItalianLabelsHandler(on_tool_start=progress)
    run = SimpleNamespace(name="get_liturgical_readings", run_type="tool")

    async def worker():
        await handler._start_trace(run)
        await handler._end_trace(run)

    await asyncio.to_thread(lambda: asyncio.run(worker()))
    assert observed == [owner, owner, owner]
    assert run.name == "get_liturgical_readings"
