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
