"""Consumer constraints that a generic dict or obsolete contract would miss."""

from copy import deepcopy

import pytest
from pydantic import ValidationError

from models import DailyMassResultContract, HomilySuccessContract, PreferencesContract, inline_schema


def test_inline_schema_retains_title_property():
    section = inline_schema(HomilySuccessContract)["properties"]["data"]["properties"]["homily"]["properties"]["introduction"]
    assert set(section["properties"]) == {"title", "content"}


@pytest.mark.parametrize("preferences", [{"style": "narrative"}, {"audience": "youth"}, {"language": "en"}])
def test_unsupported_preference_names_are_not_advertised(preferences):
    with pytest.raises(ValidationError):
        PreferencesContract.model_validate(preferences)


@pytest.mark.parametrize("mutation", ["missing_second", "blank_second", "nested_readings", "missing_metadata"])
def test_daily_consumer_rejects_incomplete_or_obsolete_shape(mutation):
    from test_liturgy_contract import load_contract

    method = next(m for m in load_contract()["methods"] if m["name"] == "liturgy_agent.get_readings")
    payload = deepcopy(method["examples"]["response_daily_mass"]["result"])
    payload["data"]["metadata"]["sunday_or_weekday"] = "Sunday"
    second = {"reference": "2 Tm 2,8-13", "text": "second reading", "type": "Second"}
    payload["data"]["second_reading"] = second
    DailyMassResultContract.model_validate(payload)
    if mutation == "missing_second":
        payload["data"]["second_reading"] = None
    elif mutation == "blank_second":
        second["text"] = "  "
    elif mutation == "nested_readings":
        payload["data"]["readings"] = {"gospel": payload["data"].pop("gospel")}
    else:
        payload["data"].pop("metadata")
    with pytest.raises(ValidationError):
        DailyMassResultContract.model_validate(payload)


@pytest.mark.parametrize("mutation", ["object_sources", "blank_section", "old_homily"])
def test_homily_consumer_rejects_obsolete_or_blank_shape(mutation):
    from test_homily_contract import load_contract

    method = next(m for m in load_contract()["methods"] if m["name"] == "homily.generate")
    payload = deepcopy(method["examples"]["response"]["result"])
    HomilySuccessContract.model_validate(payload)
    if mutation == "object_sources":
        payload["data"]["sources"] = [{"title": "source"}]
    elif mutation == "blank_section":
        payload["data"]["homily"]["conclusion"]["content"] = "  "
    else:
        payload["data"]["homily"] = {"title": "old", "content": "text", "word_count": 800}
    with pytest.raises(ValidationError):
        HomilySuccessContract.model_validate(payload)
