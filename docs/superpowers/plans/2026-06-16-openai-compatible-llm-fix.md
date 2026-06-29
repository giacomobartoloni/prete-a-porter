# OpenAI-Compatible LLM Fix Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `chat-orchestrator` use OpenAI-compatible providers configured with `OPENAI_API_KEY`, `OPENAI_MODEL_NAME`, and `OPENAI_BASE_URL`.

**Architecture:** The LLM provider selection lives in the shared `a2a_protocol.llm` factory, so provider construction and diagnostics belong there. The `chat-orchestrator` Docker runtime must install the OpenAI provider dependency explicitly instead of relying on an optional extra that is present in a lockfile but not enabled by `uv sync --frozen`.

**Tech Stack:** Python 3.12, uv, LangChain, `langchain-openai`, Docker Compose, pytest.

---

## File Structure

- Modify: `packages/a2a-protocol/src/a2a_protocol/llm.py`
- Add: `packages/a2a-protocol/tests/test_llm_factory.py`
- Modify: `packages/chat-orchestrator/pyproject.toml`
- Modify: `packages/chat-orchestrator/uv.lock`
- Optional if OpenAI should also be available inside Liturgy Agent: `packages/liturgy-agent/pyproject.toml`
- Optional if OpenAI should also be available inside Liturgy Agent: `packages/liturgy-agent/uv.lock`

---

### Task 1: Add Regression Tests For OpenAI-Compatible Factory

**Files:**
- Add: `packages/a2a-protocol/tests/test_llm_factory.py`

- [ ] **Step 1: Create failing tests**

```python
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
```

- [ ] **Step 2: Run tests and confirm failure**

Run:

```bash
pytest packages/a2a-protocol/tests/test_llm_factory.py -v
```

Expected:

```text
FAILED test_create_llm_passes_openai_base_url
FAILED test_create_llm_error_explains_missing_openai_dependency
```

---

### Task 2: Fix `OPENAI_BASE_URL` And Provider Error Message

**Files:**
- Modify: `packages/a2a-protocol/src/a2a_protocol/llm.py`

- [ ] **Step 1: Update provider list**

Use package names for better diagnostics:

```python
    providers = [
        ("ANTHROPIC_API_KEY", _create_anthropic, "langchain_anthropic"),
        ("GOOGLE_API_KEY", _create_google, "langchain_google_genai"),
        ("OPENAI_API_KEY", _create_openai, "langchain_openai"),
    ]
```

- [ ] **Step 2: Update `create_llm()` provider loop**

Replace the provider loop and strict error branch with this behavior:

```python
    provider_errors = []

    for env_var, factory, package_name in providers:
        api_key = os.getenv(env_var)
        if api_key:
            llm = factory(api_key)
            if llm:
                return llm
            provider_errors.append(f"{env_var} is set but {package_name} is not installed")

    if strict:
        if provider_errors:
            raise LLMNotConfiguredError("; ".join(provider_errors))
        raise LLMNotConfiguredError("No LLM API key configured")
```

- [ ] **Step 3: Update `_create_openai()`**

```python
def _create_openai(api_key: str) -> object | None:
    model = os.getenv("OPENAI_MODEL_NAME", "gpt-4-turbo-preview")
    base_url = os.getenv("OPENAI_BASE_URL")
    try:
        from langchain_openai import ChatOpenAI
        kwargs = {"model": model, "api_key": api_key}
        if base_url:
            kwargs["base_url"] = base_url
        return ChatOpenAI(**kwargs)
    except ImportError:
        logger.warning("langchain_openai not available")
        return None
```

- [ ] **Step 4: Run targeted tests**

Run:

```bash
pytest packages/a2a-protocol/tests/test_llm_factory.py -v
```

Expected:

```text
3 passed
```

---

### Task 3: Install OpenAI Provider In Chat Orchestrator Runtime

**Files:**
- Modify: `packages/chat-orchestrator/pyproject.toml`
- Modify: `packages/chat-orchestrator/uv.lock`

- [ ] **Step 1: Update dependency**

In `packages/chat-orchestrator/pyproject.toml`, change:

```toml
"a2a-protocol",
```

to:

```toml
"a2a-protocol[openai]",
```

Keep existing `langchain-google-genai` unchanged to minimize risk.

- [ ] **Step 2: Update lockfile**

Run from `packages/chat-orchestrator`:

```bash
uv lock
```

Expected: `packages/chat-orchestrator/uv.lock` changes and `langchain-openai` becomes part of the installed dependency graph, not only an unused optional-extra marker.

- [ ] **Step 3: Verify local dependency resolution**

Run from `packages/chat-orchestrator`:

```bash
uv sync --frozen
```

Expected: command exits successfully. It may install packages or report that the environment is already up to date.

---

### Task 4: Run Python Test Suite For Touched Packages

**Files:**
- Test only.

- [ ] **Step 1: Run A2A protocol tests**

```bash
pytest packages/a2a-protocol/tests/ -v
```

Expected:

```text
passed
```

- [ ] **Step 2: Run chat orchestrator tests**

```bash
pytest packages/chat-orchestrator/tests/ -v
```

Expected:

```text
passed
```

---

### Task 5: Verify Docker Runtime Matches The Fix

**Files:**
- Docker runtime only.

- [ ] **Step 1: Rebuild chat orchestrator**

```bash
docker compose build chat-orchestrator
```

Expected:

```text
Successfully built
```

- [ ] **Step 2: Restart service**

```bash
docker compose up -d chat-orchestrator
```

Expected:

```text
Container ... Started
```

- [ ] **Step 3: Verify env and dependency without printing secrets**

```bash
docker compose exec chat-orchestrator uv run python -c 'import importlib.util, os; print("OPENAI_API_KEY:", "SET" if os.getenv("OPENAI_API_KEY") else "UNSET"); print("OPENAI_BASE_URL:", "SET" if os.getenv("OPENAI_BASE_URL") else "UNSET"); print("OPENAI_MODEL_NAME:", "SET" if os.getenv("OPENAI_MODEL_NAME") else "UNSET"); print("langchain_openai:", "INSTALLED" if importlib.util.find_spec("langchain_openai") else "MISSING")'
```

Expected:

```text
OPENAI_API_KEY: SET
OPENAI_BASE_URL: SET
OPENAI_MODEL_NAME: SET
langchain_openai: INSTALLED
```

- [ ] **Step 4: Verify factory instantiation without calling the model**

```bash
docker compose exec chat-orchestrator uv run python -c 'from a2a_protocol.llm import create_llm; llm = create_llm(); print(type(llm).__module__, type(llm).__name__)'
```

Expected: class name should be `ChatOpenAI`. The exact module string may vary by LangChain version.

```text
... ChatOpenAI
```

---

### Task 6: Optional Follow-Up For Liturgy Agent

**Files:**
- Modify: `packages/liturgy-agent/pyproject.toml`
- Modify: `packages/liturgy-agent/uv.lock`

Reason: `liturgy-agent` also calls `create_llm(strict=False)`. With only `OPENAI_API_KEY` set and no `langchain-openai`, it silently falls back to `MagicMock`.

- [ ] **Step 1: Update dependency**

In `packages/liturgy-agent/pyproject.toml`, change:

```toml
"a2a-protocol",
```

to:

```toml
"a2a-protocol[openai]",
```

- [ ] **Step 2: Update lockfile**

Run from `packages/liturgy-agent`:

```bash
uv lock
```

- [ ] **Step 3: Rebuild and verify**

```bash
docker compose build liturgy-agent
docker compose up -d liturgy-agent
docker compose exec liturgy-agent uv run python -c 'import importlib.util; print("langchain_openai:", "INSTALLED" if importlib.util.find_spec("langchain_openai") else "MISSING")'
```

Expected:

```text
langchain_openai: INSTALLED
```

---

### Task 7: Commit

**Files:**
- `packages/a2a-protocol/src/a2a_protocol/llm.py`
- `packages/a2a-protocol/tests/test_llm_factory.py`
- `packages/chat-orchestrator/pyproject.toml`
- `packages/chat-orchestrator/uv.lock`
- Optional: `packages/liturgy-agent/pyproject.toml`
- Optional: `packages/liturgy-agent/uv.lock`

- [ ] **Step 1: Review diff**

```bash
git diff
```

Expected: only the files above changed, plus this plan if it is being committed.

- [ ] **Step 2: Commit main fix**

```bash
git add packages/a2a-protocol/src/a2a_protocol/llm.py packages/a2a-protocol/tests/test_llm_factory.py packages/chat-orchestrator/pyproject.toml packages/chat-orchestrator/uv.lock docs/superpowers/plans/2026-06-16-openai-compatible-llm-fix.md
git commit -m "fix(llm): enable OpenAI-compatible provider"
```

- [ ] **Step 3: Commit optional Liturgy Agent follow-up if included**

```bash
git add packages/liturgy-agent/pyproject.toml packages/liturgy-agent/uv.lock
git commit -m "fix(liturgy): install OpenAI provider dependency"
```

---

## Notes

- The previous successful test can be real if it used a different environment, such as a local virtualenv with `langchain-openai` installed, a stale Docker image, or a provider with higher priority such as Anthropic or Google.
- The current Docker runtime confirms that `OPENAI_API_KEY`, `OPENAI_BASE_URL`, and `OPENAI_MODEL_NAME` are present.
- The current hard failure is that `langchain_openai` is missing from the `chat-orchestrator` runtime environment.
- The current latent bug is that `_create_openai()` ignores `OPENAI_BASE_URL`, so OpenAI-compatible endpoints are not actually configured.

---

## Self-Review

- Spec coverage: The plan covers dependency installation, `OPENAI_BASE_URL` propagation, diagnostics, tests, Docker verification, and an optional Liturgy Agent follow-up.
- Placeholder scan: No task depends on `TBD`, vague validation, or unspecified tests.
- Type consistency: The plan consistently uses `create_llm()`, `LLMNotConfiguredError`, `OPENAI_BASE_URL`, and `ChatOpenAI` as defined in the current codebase.
