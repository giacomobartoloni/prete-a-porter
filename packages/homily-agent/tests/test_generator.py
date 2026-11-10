"""Generation must use model output, preserve context and enforce bounded validation."""

import json

import pytest
from langchain_core.messages import AIMessage
from pydantic import ValidationError

from homily_agent.generator import HomilyGenerator
from homily_agent.rag.retrieval import RetrievedDocument
from homily_agent.state import LiturgicalReading, UserPreferences


def readings():
    return LiturgicalReading(
        date="2026-11-01",
        first_reading={"reference": "Ap 7", "text": "UNA MOLTITUDINE DI OGNI NAZIONE", "type": "First"},
        gospel={"reference": "Mt 5", "text": "BEATI GLI OPERATORI DI PACE", "type": "Gospel"},
    )


def response(words=200, used=None):
    names = ["introduction", "reading_reflection", "practical_application", "conclusion"]
    return {
        **{key: {"title": key, "content": " ".join(["pace"] * (words // 4))} for key in names},
        "used_source_ids": used or [],
    }


class Model:
    def __init__(self, *outputs):
        self.outputs = list(outputs)
        self.requests = []

    def invoke(self, messages):
        self.requests.append(messages)
        value = self.outputs[min(len(self.requests) - 1, len(self.outputs) - 1)]
        if isinstance(value, Exception):
            raise value
        return AIMessage(content=value if isinstance(value, (str, list)) else json.dumps(value))


class Corpus:
    def retrieve(self, query):
        return [
            RetrievedDocument(
                content="MISERICORDIA NELLA COMUNITA", source="CCC", score=0.9, metadata={"paragraph_num": 2447}
            )
        ]


def test_generation_uses_full_readings_preferences_and_selected_sources():
    llm = Model(response(200, ["S1", "invented", "S1"]))
    prefs = UserPreferences(
        target_audience="youth",
        target_word_count=200,
        instructions="Santi: un esempio concreto tra fratelli",
        themes=["pace"],
    )
    homily, sources = HomilyGenerator(Corpus(), llm=llm).generate(readings(), "mass", prefs)
    request = json.loads(llm.requests[0][-1].content)
    assert request["readings"]["gospel"]["text"] == "BEATI GLI OPERATORI DI PACE"
    assert request["readings"]["first_reading"]["text"] == "UNA MOLTITUDINE DI OGNI NAZIONE"
    assert request["preferences"]["target_audience"] == "youth"
    assert request["preferences"]["instructions"] == "Santi: un esempio concreto tra fratelli"
    assert request["target_word_count"] == 200
    assert request["sources"][0]["content"] == "MISERICORDIA NELLA COMUNITA"
    assert homily.introduction.content == " ".join(["pace"] * 50)
    assert sources == ["CCC §2447"]


def test_revision_receives_complete_draft_and_explicit_instruction():
    llm = Model(response())
    draft = "Bozza originale: due amici a scuola, poi fanno pace."
    HomilyGenerator(llm=llm).generate(
        readings(),
        "mass",
        UserPreferences(target_word_count=200, instructions="Sostituisci scuola con fratelli"),
        existing_draft=draft,
    )
    request = json.loads(llm.requests[0][-1].content)
    assert request["existing_draft"] == draft
    assert request["operation"] == "refine"
    assert request["preferences"]["instructions"] == "Sostituisci scuola con fratelli"


@pytest.mark.parametrize(
    "invalid", ["not json", response(20), response(200) | {"conclusion": {"title": "fine", "content": "  "}}]
)
def test_invalid_output_gets_only_one_corrective_attempt(invalid):
    llm = Model(invalid, response())
    homily, _ = HomilyGenerator(llm=llm).generate(readings(), "mass", UserPreferences(target_word_count=200))
    assert homily.conclusion.content.strip()
    assert len(llm.requests) == 2
    assert "correction" in json.loads(llm.requests[1][-1].content)


def test_persistent_bad_output_fails_without_template_fallback():
    llm = Model("bad")
    with pytest.raises(ValueError, match="valid homily"):
        HomilyGenerator(llm=llm).generate(readings(), "mass", UserPreferences(target_word_count=200))
    assert len(llm.requests) == 2


def test_provider_failure_does_not_retry_or_expose_details():
    llm = Model(RuntimeError("private-provider-token"))
    with pytest.raises(RuntimeError, match="model is unavailable") as error:
        HomilyGenerator(llm=llm).generate(readings(), "mass", UserPreferences())
    assert "private-provider-token" not in str(error.value)
    assert len(llm.requests) == 1


def test_source_context_is_bounded():
    class LargeCorpus:
        def retrieve(self, query):
            return [RetrievedDocument("a" * 8000, f"source-{i}", 0.9, {}) for i in range(12)]

    llm = Model(response())
    HomilyGenerator(LargeCorpus(), llm=llm).generate(readings(), "mass", UserPreferences(target_word_count=200))
    sources = json.loads(llm.requests[0][-1].content)["sources"]
    assert sum(len(s["content"]) for s in sources) <= 12000
    assert all(len(s["content"]) <= 2500 for s in sources)


def test_provider_text_blocks_and_json_fence_are_supported():
    text = "```json\n" + json.dumps(response()) + "\n```"
    llm = Model([{"type": "text", "text": text}])
    homily, _ = HomilyGenerator(llm=llm).generate(readings(), "mass", UserPreferences(target_word_count=200))
    assert homily.conclusion.content.strip()


@pytest.mark.parametrize("count", [49, 3001, True])
def test_invalid_explicit_word_count_is_rejected(count):
    with pytest.raises(ValidationError):
        UserPreferences(target_word_count=count)


def test_oversized_instructions_are_rejected():
    with pytest.raises(ValidationError):
        UserPreferences(instructions="x" * 4001)


def test_fixture_mode_runs_real_generator_without_provider(monkeypatch):
    monkeypatch.setenv("TEST_MODE", "true")
    homily, _ = HomilyGenerator().generate(readings(), "mass", UserPreferences(target_word_count=200))
    contents = " ".join(
        getattr(homily, k).content
        for k in ["introduction", "reading_reflection", "practical_application", "conclusion"]
    )
    assert 170 <= len(contents.split()) <= 230
    assert "fixture" in contents.lower()


@pytest.mark.asyncio
async def test_compiled_graph_does_not_block_event_loop():
    import asyncio
    import threading

    from homily_agent.graph import create_homily_graph
    from homily_agent.state import HomilyAgentState

    loop_thread = threading.get_ident()
    worker_threads = []

    class ObservedModel(Model):
        def invoke(self, messages):
            worker_threads.append(threading.get_ident())
            return super().invoke(messages)

    graph = create_homily_graph(generator=HomilyGenerator(llm=ObservedModel(response())))
    state = HomilyAgentState(liturgical_data=readings(), user_preferences=UserPreferences(target_word_count=200))
    output = await asyncio.wait_for(graph.ainvoke({"homily_state": state}), timeout=3)
    assert output["homily_state"].generated_homily is not None
    assert worker_threads and loop_thread not in worker_threads


@pytest.mark.asyncio
async def test_fixture_handler_avoids_real_retrieval(monkeypatch):
    from homily_agent.main import HomilyAgentHandler

    monkeypatch.setenv("TEST_MODE", "true")
    handler = HomilyAgentHandler()
    result = await handler(
        "homily.generate", {"liturgical_data": readings().model_dump(), "preferences": {"target_word_count": 200}}
    )
    assert handler.retrieval_service is None
    assert result["status"] == "success"
    assert "fixture" in result["data"]["homily"]["introduction"]["content"]


def test_model_runtime_limits_are_configurable_and_have_portable_default(monkeypatch):
    from homily_agent import generator

    observed = {}

    def factory(**kwargs):
        observed.update(kwargs)
        return Model(response())

    monkeypatch.delenv("TEST_MODE", raising=False)
    monkeypatch.delenv("HOMILY_MAX_OUTPUT_TOKENS", raising=False)
    monkeypatch.delenv("HOMILY_MODEL_TIMEOUT_SECONDS", raising=False)
    monkeypatch.setattr(generator, "create_llm", factory)
    HomilyGenerator().generate(readings(), "mass", UserPreferences(target_word_count=200))
    assert observed == {"timeout": 45, "max_retries": 0, "max_tokens": 4096}
    monkeypatch.setenv("HOMILY_MAX_OUTPUT_TOKENS", "8192")
    monkeypatch.setenv("HOMILY_MODEL_TIMEOUT_SECONDS", "60")
    HomilyGenerator().generate(readings(), "mass", UserPreferences(target_word_count=200))
    assert observed == {"timeout": 60, "max_retries": 0, "max_tokens": 8192}


def test_optional_reasoning_control_is_explicit_and_openai_only(monkeypatch):
    from homily_agent import generator

    monkeypatch.delenv("TEST_MODE", raising=False)
    monkeypatch.setenv("HOMILY_OPENAI_REASONING_EFFORT", "none")
    bound = []

    class OpenAIModel(Model):
        __module__ = "langchain_openai.chat_models.base"

        def bind(self, **kwargs):
            bound.append(kwargs)
            return self

    monkeypatch.setattr(generator, "create_llm", lambda **kwargs: OpenAIModel(response()))
    HomilyGenerator().generate(readings(), "mass", UserPreferences(target_word_count=200))
    assert bound == [{"reasoning_effort": "none"}]
    monkeypatch.setattr(generator, "create_llm", lambda **kwargs: Model(response()))
    invalid = HomilyGenerator()
    for _ in range(2):
        with pytest.raises(ValueError, match="OpenAI-compatible"):
            invalid.generate(readings(), "mass", UserPreferences(target_word_count=200))


def test_nontext_provider_payload_gets_a_bounded_correction():
    from types import SimpleNamespace

    class NontextModel(Model):
        def invoke(self, messages):
            if not self.requests:
                self.requests.append(messages)
                return SimpleNamespace(content=None)
            return super().invoke(messages)

    model = NontextModel(response())
    homily, _ = HomilyGenerator(llm=model).generate(readings(), "mass", UserPreferences(target_word_count=200))
    assert homily.conclusion.content.strip()
    assert len(model.requests) == 2


def test_unconfigured_production_never_falls_back_to_fixture(monkeypatch):
    from a2a_protocol.llm import LLMNotConfiguredError

    for key in ["TEST_MODE", "OPENAI_API_KEY", "ANTHROPIC_API_KEY", "GOOGLE_API_KEY"]:
        monkeypatch.delenv(key, raising=False)
    with pytest.raises(LLMNotConfiguredError):
        HomilyGenerator().generate(readings(), "mass", UserPreferences(target_word_count=200))


@pytest.mark.parametrize("length,target", [("short", 650), ("medium", 1100), ("long", 1600)])
def test_legacy_length_selects_target_when_no_word_count_is_given(length, target):
    model = Model(response(target))
    homily, _ = HomilyGenerator(llm=model).generate(readings(), "mass", UserPreferences(length=length))
    assert json.loads(model.requests[0][-1].content)["target_word_count"] == target
    assert homily.introduction.content.strip()


def test_blank_draft_is_rejected_before_model_call():
    model = Model(response())
    with pytest.raises(ValueError, match="blank"):
        HomilyGenerator(llm=model).generate(
            readings(), "mass", UserPreferences(target_word_count=200), existing_draft="   "
        )
    assert model.requests == []


def test_second_oversized_draft_can_remove_only_complete_optional_sentences():
    draft = response(200)
    # 275 words: all practical narrative stays; optional sentences can be omitted.
    for key in draft:
        if key != "used_source_ids":
            draft[key]["content"] = " ".join(["pace"] * 35) + ". " + "Insieme " + " ".join(["insieme"] * 29) + "."
    draft["practical_application"]["content"] += (
        " Due fratelli litigano per un gioco e scelgono di ascoltarsi prima di chiedersi perdono sinceramente."
    )
    model = Model(draft)
    homily, _ = HomilyGenerator(llm=model).generate(readings(), "mass", UserPreferences(target_word_count=200))
    assert len(model.requests) == 2
    assert homily.practical_application.content == draft["practical_application"]["content"]
    count = sum(len(getattr(homily, key).content.split()) for key in draft if key != "used_source_ids")
    assert 170 <= count <= 230
    assert all(getattr(homily, key).content.endswith(".") for key in draft if key != "used_source_ids")


def test_oversize_without_safe_sentence_boundaries_still_fails():
    with pytest.raises(ValueError, match="valid homily"):
        HomilyGenerator(llm=Model(response(280))).generate(readings(), "mass", UserPreferences(target_word_count=200))


@pytest.mark.parametrize(
    "protected",
    [
        "«Prima frase. Seconda frase con molte parole importanti da mantenere. Ultima frase.»",
        "Mons. Rossi invita tutti i ragazzi a perdonarsi davvero.",
        "S. Paolo invita tutti i ragazzi a perdonarsi davvero.",
    ],
)
def test_sentence_fitting_never_removes_fragments_inside_quotes_or_abbreviations(protected):
    from homily_agent.composition import Draft, _fit_complete_sentences

    data = response(200)
    data["introduction"]["content"] = "Benvenuti tutti voi alla festa dei Santi. " + protected
    draft = Draft.model_validate(data)
    original = draft.introduction.content
    # A tight budget would remove the interior quote/abbreviation fragment.
    count = sum(len(getattr(draft, key).content.split()) for key in data if key != "used_source_ids")
    result = _fit_complete_sentences(draft, count - 1, count - 20)
    assert result.introduction.content == original


def test_optional_json_mode_is_bound_with_reasoning_and_rejects_other_providers(monkeypatch):
    from homily_agent import generator

    monkeypatch.delenv("TEST_MODE", raising=False)
    monkeypatch.setenv("HOMILY_OPENAI_JSON_MODE", "true")
    monkeypatch.setenv("HOMILY_OPENAI_REASONING_EFFORT", "none")
    observed = []

    class OpenAIModel(Model):
        __module__ = "langchain_openai.chat_models.base"

        def bind(self, **kwargs):
            observed.append(kwargs)
            return self

    monkeypatch.setattr(generator, "create_llm", lambda **kwargs: OpenAIModel(response()))
    HomilyGenerator().generate(readings(), "mass", UserPreferences(target_word_count=200))
    assert observed == [{"reasoning_effort": "none", "response_format": {"type": "json_object"}}]
    monkeypatch.delenv("HOMILY_OPENAI_REASONING_EFFORT")
    monkeypatch.setattr(generator, "create_llm", lambda **kwargs: Model(response()))
    with pytest.raises(ValueError, match="OpenAI-compatible"):
        HomilyGenerator().generate(readings(), "mass", UserPreferences(target_word_count=200))


def test_length_correction_edits_rejected_prose_without_repeating_original_draft():
    model = Model(response(280), response())
    prefs = UserPreferences(target_word_count=200, instructions="Sostituisci scuola con una lite tra fratelli")
    HomilyGenerator(llm=model).generate(readings(), "mass", prefs, existing_draft="UNIQUE_ORIGINAL_DRAFT")
    corrective = "\n".join(message.content for message in model.requests[1])
    assert "UNIQUE_ORIGINAL_DRAFT" not in corrective
    assert "UNA MOLTITUDINE DI OGNI NAZIONE" not in corrective
    assert "lite tra fratelli" in corrective
    assert "pace" in corrective
