import builtins
import sys
import types

import pytest

from a2a_protocol.llm import LLMNotConfiguredError, create_llm


LLM_ENV_VARS = [
    "ANTHROPIC_API_KEY",
    "ANTHROPIC_MODEL_NAME",
    "GOOGLE_API_KEY",
    "GOOGLE_MODEL_NAME",
    "OPENAI_API_KEY",
    "OPENAI_MODEL_NAME",
    "OPENAI_BASE_URL",
    "TEST_MODE",
]


@pytest.fixture(autouse=True)
def clear_llm_env(monkeypatch):
    for env_var in LLM_ENV_VARS:
        monkeypatch.delenv(env_var, raising=False)


def test_create_llm_passes_openai_base_url(monkeypatch):
    created_kwargs = {}

    class FakeChatOpenAI:
        def __init__(self, **kwargs):
            created_kwargs.update(kwargs)

    fake_module = types.SimpleNamespace(ChatOpenAI=FakeChatOpenAI)

    monkeypatch.setitem(sys.modules, "langchain_openai", fake_module)
    monkeypatch.setenv("OPENAI_API_KEY", "test-api-key")
    monkeypatch.setenv("OPENAI_MODEL_NAME", "test-model")
    monkeypatch.setenv("OPENAI_BASE_URL", "https://compatible.example/v1")

    llm = create_llm()

    assert isinstance(llm, FakeChatOpenAI)
    assert created_kwargs == {
        "model": "test-model",
        "api_key": "test-api-key",
        "base_url": "https://compatible.example/v1",
    }


def test_create_llm_omits_openai_base_url_when_unset(monkeypatch):
    created_kwargs = {}

    class FakeChatOpenAI:
        def __init__(self, **kwargs):
            created_kwargs.update(kwargs)

    fake_module = types.SimpleNamespace(ChatOpenAI=FakeChatOpenAI)

    monkeypatch.setitem(sys.modules, "langchain_openai", fake_module)
    monkeypatch.setenv("OPENAI_API_KEY", "test-api-key")
    monkeypatch.setenv("OPENAI_MODEL_NAME", "test-model")

    llm = create_llm()

    assert isinstance(llm, FakeChatOpenAI)
    assert created_kwargs == {
        "model": "test-model",
        "api_key": "test-api-key",
    }


def test_create_llm_error_explains_missing_openai_dependency(monkeypatch):
    original_import = builtins.__import__

    def fake_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "langchain_openai":
            raise ImportError("No module named langchain_openai")
        return original_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    monkeypatch.setenv("OPENAI_API_KEY", "test-api-key")

    with pytest.raises(LLMNotConfiguredError) as excinfo:
        create_llm()

    assert "OPENAI_API_KEY is set but langchain_openai is not installed" in str(excinfo.value)
