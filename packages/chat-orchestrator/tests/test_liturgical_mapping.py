"""Contract tests for the liturgical payload the orchestrator forwards to the homily agent.

The homily agent validates `liturgical_data` against LiturgicalReading/Reading, so anything a
model compacts on its way through `generate_homily` (bare reference strings, partial metadata)
must be repaired here — otherwise homily.generate dies with a pydantic ValidationError.
"""

from chat_orchestrator import tools

VALID_METADATA = {
    "date": "2026-09-20",
    "occasion": "mass",
    "season": "Ordinary",
    "color": "Green",
    "year_cycle": "A",
    "sunday_or_weekday": "Sunday",
}


def test_compact_string_readings_are_expanded():
    mapped = tools._map_liturgical_data(
        {
            "date": "2026-09-20",
            "occasion": "mass",
            "first_reading": "Isaia 55,6-9",
            "gospel": "Matteo 20,1-16a",
        }
    )

    assert mapped["first_reading"] == {"reference": "Isaia 55,6-9", "text": "", "type": "First"}
    assert mapped["gospel"] == {"reference": "Matteo 20,1-16a", "text": "", "type": "Gospel"}
    assert "psalm" not in mapped


def test_nested_agent_payload_keeps_readings_and_metadata():
    mapped = tools._map_liturgical_data(
        {
            "status": "success",
            "source": "evangelizo.org",
            "data": {
                "date": "2026-09-20",
                "occasion": "mass",
                "metadata": VALID_METADATA,
                "first_reading": {"reference": "Isaia 55,6-9", "text": "Cercate il Signore", "type": "First"},
                "gospel": {"reference": "Matteo 20,1-16a", "text": "Il regno dei cieli", "type": "Gospel"},
            },
        }
    )

    assert mapped["gospel"]["text"] == "Il regno dei cieli"
    assert mapped["metadata"]["year_cycle"] == "A"


def test_metadata_missing_required_fields_is_dropped():
    mapped = tools._map_liturgical_data(
        {
            "date": "2026-09-20",
            "occasion": "mass",
            "metadata": {"season": "Tempo Ordinario", "color": "verde"},
            "gospel": {"reference": "Matteo 20,1-16a", "text": "..."},
        }
    )

    assert "metadata" not in mapped
    assert mapped["gospel"]["reference"] == "Matteo 20,1-16a"


def test_reading_without_reference_is_dropped():
    mapped = tools._map_liturgical_data({"gospel": {"text": "solo testo, nessun riferimento"}})

    assert "gospel" not in mapped


async def test_missing_texts_and_metadata_are_recovered_from_the_liturgy_agent(monkeypatch):
    calls = []

    async def fake_request_liturgical_data(occasion, date):
        calls.append((occasion, date))
        return {
            "data": {
                "date": "2026-09-20",
                "occasion": "mass",
                "metadata": VALID_METADATA,
                "first_reading": {"reference": "Isaia 55,6-9", "text": "Cercate il Signore", "type": "First"},
                "gospel": {"reference": "Matteo 20,1-16a", "text": "Il regno dei cieli", "type": "Gospel"},
            }
        }

    monkeypatch.setattr(tools, "request_liturgical_data", fake_request_liturgical_data)

    compact = tools._map_liturgical_data(
        {
            "date": "2026-09-20",
            "occasion": "mass",
            "first_reading": "Isaia 55,6-9",
            "gospel": "Matteo 20,1-16a",
        }
    )
    mapped = await tools._with_full_reading_texts(compact, "mass")

    assert calls == [("mass", "2026-09-20")]
    assert mapped["first_reading"]["text"] == "Cercate il Signore"
    assert mapped["gospel"]["text"] == "Il regno dei cieli"
    assert mapped["metadata"]["season"] == "Ordinary"


async def test_recovery_is_skipped_when_texts_are_already_present(monkeypatch):
    async def fail_if_called(occasion, date):
        raise AssertionError("liturgy agent must not be called when readings carry their texts")

    monkeypatch.setattr(tools, "request_liturgical_data", fail_if_called)

    payload = {
        "date": "2026-09-20",
        "occasion": "mass",
        "metadata": VALID_METADATA,
        "first_reading": {"reference": "Isaia 55,6-9", "text": "Cercate il Signore", "type": "First"},
        "gospel": {"reference": "Matteo 20,1-16a", "text": "Il regno dei cieli", "type": "Gospel"},
    }

    mapped = await tools._with_full_reading_texts(tools._map_liturgical_data(payload), "mass")

    assert mapped["gospel"]["text"] == "Il regno dei cieli"
