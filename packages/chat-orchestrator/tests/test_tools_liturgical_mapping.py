"""The liturgical-data mapper must always produce homily-agent-shaped readings.

The LLM echoes the liturgical object back as a JSON string when it calls
``generate_homily``, and it drops fields it considers decorative. ``type`` is one
of them, and the homily agent's ``LiturgicalReading`` requires it — a missing
``type`` made generation fail with an opaque "Internal error" the model could not
recover from, so no homily was ever produced through the tool.
"""

from chat_orchestrator.tools import _map_liturgical_data


def _reading(reference: str) -> dict:
    return {"reference": reference, "text": f"testo di {reference}"}


def _full_response() -> dict:
    """The shape liturgy-agent returns, wrapped in its A2A envelope."""
    return {
        "status": "success",
        "data": {
            "date": "2026-09-20",
            "occasion": "mass",
            "metadata": {"date": "2026-09-20", "occasion": "mass"},
            "first_reading": {**_reading("Isaia 55,6-9"), "type": "First"},
            "psalm": {**_reading("Salmi 145"), "type": "Psalm"},
            "second_reading": {**_reading("Filippesi 1,20c-24"), "type": "Second"},
            "gospel": {**_reading("Matteo 21,28-32"), "type": "Gospel"},
        },
    }


class TestTopLevelReadings:
    """The branch the LLM actually produces: readings already at top level."""

    def test_type_is_added_when_the_llm_drops_it(self):
        """This is the regression: the old mapper left type missing here."""
        payload = {
            "first_reading": _reading("Isaia 55,6-9"),
            "psalm": _reading("Salmi 145"),
            "gospel": _reading("Matteo 21,28-32"),
        }
        mapped = _map_liturgical_data(payload)
        assert mapped["first_reading"]["type"] == "First"
        assert mapped["psalm"]["type"] == "Psalm"
        assert mapped["gospel"]["type"] == "Gospel"

    def test_existing_type_is_not_overwritten(self):
        payload = {"gospel": {**_reading("Matteo 21,28-32"), "type": "Gospel"}}
        assert _map_liturgical_data(payload)["gospel"]["type"] == "Gospel"

    def test_missing_text_is_backfilled(self):
        payload = {"first_reading": {"reference": "Isaia 55,6-9"}}
        assert _map_liturgical_data(payload)["first_reading"]["text"] == ""

    def test_all_four_readings_are_typed(self):
        """Every reading the liturgy agent can emit must satisfy the homily agent."""
        payload = {
            "first_reading": _reading("a"),
            "psalm": _reading("b"),
            "second_reading": _reading("c"),
            "gospel": _reading("d"),
        }
        mapped = _map_liturgical_data(payload)
        assert [mapped[k]["type"] for k in ("first_reading", "psalm", "second_reading", "gospel")] == [
            "First",
            "Psalm",
            "Second",
            "Gospel",
        ]


class TestStringifiedReadings:
    """Some models compress a reading to its bare reference."""

    def test_string_reading_becomes_an_object(self):
        payload = {
            "first_reading": "Isaia 55,6-9",
            "psalm": "Salmi 145",
            "second_reading": "Filippesi 1,20c-24.27a",
            "gospel": "Matteo 20,1-16a",
        }
        mapped = _map_liturgical_data(payload)
        assert mapped["first_reading"] == {"reference": "Isaia 55,6-9", "text": "", "type": "First"}
        assert mapped["gospel"]["type"] == "Gospel"

    def test_every_reading_survives_as_a_dict(self):
        payload = {"first_reading": "a", "psalm": "b", "second_reading": "c", "gospel": "d"}
        mapped = _map_liturgical_data(payload)
        assert all(isinstance(mapped[k], dict) for k, _ in
                   [("first_reading", 0), ("psalm", 0), ("second_reading", 0), ("gospel", 0)])

    def test_mixed_string_and_object_readings(self):
        payload = {"first_reading": "Isaia 55,6-9", "gospel": _reading("Matteo 20,1-16a")}
        mapped = _map_liturgical_data(payload)
        assert mapped["first_reading"]["reference"] == "Isaia 55,6-9"
        assert mapped["gospel"]["reference"] == "Matteo 20,1-16a"


class TestEnvelopeForm:
    """The full A2A envelope, where readings sit under data."""

    def test_readings_under_data_are_typed(self):
        mapped = _map_liturgical_data(_full_response())
        assert mapped["first_reading"]["type"] == "First"
        assert mapped["gospel"]["type"] == "Gospel"

    def test_absent_readings_are_not_invented(self):
        """A weekday with no second reading must not gain one."""
        payload = {"first_reading": _reading("a"), "gospel": _reading("d")}
        mapped = _map_liturgical_data(payload)
        assert "second_reading" not in mapped


class TestNestedReadingsForm:
    """The liturgy agent's contract shape, where readings sit under readings."""

    def test_readings_under_readings_are_typed(self):
        payload = {
            "date": "2026-09-20",
            "occasion": "mass",
            "metadata": {},
            "readings": {
                "first_reading": _reading("a"),
                "gospel": _reading("d"),
            },
        }
        mapped = _map_liturgical_data(payload)
        assert mapped["first_reading"]["type"] == "First"
        assert mapped["gospel"]["type"] == "Gospel"
