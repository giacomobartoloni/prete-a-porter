"""Refinement actions: typed payloads and the composed Italian messages."""

from prete_chat import actions


class TestMessageFor:
    def test_every_action_has_a_message(self):
        for action in actions.refinement_actions():
            operation = action.payload["operation"]
            assert actions.message_for(operation)

    def test_unknown_operations_yield_none(self):
        assert actions.message_for("esplodi") is None
        assert actions.message_for(None) is None
        assert actions.message_for(7) is None

    def test_messages_are_distinct(self):
        messages = [actions.message_for(operation) for operation, _label in actions.ACTION_LABELS]
        assert len(set(messages)) == len(messages)


class TestRefinementActions:
    def test_all_actions_share_the_callback_name(self):
        assert {action.name for action in actions.refinement_actions()} == {"refine_homily"}

    def test_fresh_instances_per_message(self):
        """Chainlit sends actions with their message: ids must not be reused."""
        first = {action.id for action in actions.refinement_actions()}
        second = {action.id for action in actions.refinement_actions()}
        assert first.isdisjoint(second)
