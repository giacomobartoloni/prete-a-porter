"""Italian controls mapped to the core's typed preferences (plan §18)."""

from chat_orchestrator.application import ChatPreferences

from prete_chat import preferences


class TestFromSettings:
    def test_full_selection_maps_to_the_core_model(self):
        selected = preferences.from_settings(
            {"target_audience": "youth", "tone": "poetic", "length": "long"}
        )
        assert selected is not None
        assert selected.model_dump() == {"target_audience": "youth", "tone": "poetic", "length": "long"}

    def test_partial_selection_keeps_only_chosen_fields(self):
        selected = preferences.from_settings({"tone": "conversational"})
        assert selected is not None
        assert selected.model_dump(exclude_none=True) == {"tone": "conversational"}

    def test_untouched_settings_pin_nothing(self):
        assert preferences.from_settings({}) is None
        assert preferences.from_settings(None) is None

    def test_unknown_ids_and_values_are_ignored(self):
        assert preferences.from_settings({"destinatari": "adulti", "tone": "urlante"}) is None
        selected = preferences.from_settings({"tone": "formal", "bogus": 1})
        assert selected is not None
        assert selected.model_dump(exclude_none=True) == {"tone": "formal"}


class TestWidgets:
    def test_widgets_cover_the_three_core_fields(self):
        assert [widget.id for widget in preferences.settings_widgets()] == ["target_audience", "tone", "length"]

    def test_every_widget_option_is_accepted_by_the_core(self):
        """Drift guard: the selects and the core literals cannot diverge."""
        for widget in preferences.settings_widgets():
            for value in widget.items.values():
                ChatPreferences(**{widget.id: value})

    def test_options_are_labelled_in_italian_and_valued_in_core_terms(self):
        for widget in preferences.settings_widgets():
            for label, value in widget.items.items():
                assert label != value
                assert value.isascii() and value.islower()
