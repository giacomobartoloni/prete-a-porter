# LLM Env Var Configuration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make LLM API endpoint (base URL) and model name configurable via environment variables, alongside existing API keys. Group providers by API standard instead of per-vendor.

**Architecture:** Consolidate from 4 providers (Anthropic, Google, OpenAI, Fireworks) to 3 API-standard families (Anthropic, Google, OpenAI-compatible). Each factory function reads model name from a provider-specific env var; base URLs are already natively supported by `ChatAnthropic` (`ANTHROPIC_BASE_URL`) and `ChatOpenAI` (`OPENAI_BASE_URL`). Remove `_create_fireworks` — Fireworks is just `ChatOpenAI` with a different `base_url`.

**Tech Stack:** Python 3.12+, `langchain-anthropic`, `langchain-google-genai`, `langchain-openai`

---

## File Structure

| File | Action | Responsibility |
|------|--------|---------------|
| `packages/a2a-protocol/src/a2a_protocol/llm.py` | Modify | LLM factory — remove `preferred_model`, remove `_create_fireworks`, add env-var-driven model names |
| `packages/a2a-protocol/pyproject.toml` | Modify | Remove `fireworks = ["langchain-fireworks"]` optional dep |
| `.env.example` | Modify | Document new env vars with examples for OpenAI-compatible providers |
| `AGENTS.md` | Modify | Update section 8 "Configuration" with provider selection docs and env var table |
| `packages/chat-orchestrator/src/chat_orchestrator/config.py` | Check/Modify | Verify no `prefer_google` usage; update if needed |
| `packages/liturgy-agent/src/liturgy_agent/main.py` | None needed | Calls `create_llm(strict=False)` — no change needed |
| `packages/a2a-protocol/src/a2a_protocol/__init__.py` | None needed | Exports `create_llm` — signature change is backward-compatible for existing consumers |
| `docs/plans/refactoring-plan.md` | None needed | Archived document, already stale |

---

### Task 1: Update LLM factory (`llm.py`)

**Files:**
- Modify: `packages/a2a-protocol/src/a2a_protocol/llm.py` (entire file)

- [ ] **Step 1: Read current file**

Run: `cat packages/a2a-protocol/src/a2a_protocol/llm.py`

- [ ] **Step 2: Rewrite `llm.py`**

Replace the entire file content with:

```python
"""
Shared LLM factory for all agents.

Provides a unified way to create LLM instances based on environment
configuration. Each agent can specialize the factory for its needs.

Provider selection is by API-standard family, in priority order:
  1. Anthropic (Claude) — chat API
  2. Google (Gemini)    — generative AI API
  3. OpenAI-compatible  — OpenAI / Fireworks / Groq / Together / Ollama / vLLM

The first provider with an API key set wins.
"""

import os
import logging

logger = logging.getLogger(__name__)


class LLMNotConfiguredError(Exception):
    """Raised when no LLM API key is configured."""
    pass


def create_llm(strict: bool = True) -> object:
    """Create an LLM instance based on available API keys.

    Checks ANTHROPIC_API_KEY, GOOGLE_API_KEY, OPENAI_API_KEY
    in priority order. Uses the FIRST provider with a key set.

    Each provider reads its model name and base URL from env vars:
      - Anthropic: ANTHROPIC_MODEL_NAME, ANTHROPIC_BASE_URL
      - Google:    GOOGLE_MODEL_NAME
      - OpenAI:    OPENAI_MODEL_NAME, OPENAI_BASE_URL

    Args:
        strict: If True, raise LLMNotConfiguredError when no key is found.
                If False, return a MagicMock fallback.

    Returns:
        Configured LLM instance (ChatAnthropic, ChatGoogleGenerativeAI,
        or ChatOpenAI).

    Raises:
        LLMNotConfiguredError: If strict=True and no API key is available.
    """
    if os.getenv("TEST_MODE") == "true":
        from unittest.mock import AsyncMock
        mock_llm = AsyncMock()
        mock_llm.bind_tools.return_value = mock_llm
        mock_response = AsyncMock()
        mock_response.content = "Test response from mock LLM"
        mock_response.tool_calls = []
        mock_llm.invoke.return_value = mock_response
        mock_llm.ainvoke.return_value = mock_response
        logger.debug("Using mock LLM for testing")
        return mock_llm

    providers = [
        ("ANTHROPIC_API_KEY", _create_anthropic),
        ("GOOGLE_API_KEY", _create_google),
        ("OPENAI_API_KEY", _create_openai),
    ]

    for env_var, factory in providers:
        api_key = os.getenv(env_var)
        if api_key:
            llm = factory(api_key)
            if llm:
                return llm

    if strict:
        raise LLMNotConfiguredError()

    from unittest.mock import MagicMock
    logger.warning("No LLM API key configured, using mock LLM")
    return MagicMock()


def _create_anthropic(api_key: str) -> object | None:
    try:
        from langchain_anthropic import ChatAnthropic
        model = os.getenv("ANTHROPIC_MODEL_NAME") or "claude-3-5-sonnet-20241022"
        return ChatAnthropic(model_name=model, api_key=api_key)
    except ImportError:
        logger.warning("langchain_anthropic not available")
        return None


def _create_google(api_key: str) -> object | None:
    try:
        from langchain_google_genai import ChatGoogleGenerativeAI
        model = os.getenv("GOOGLE_MODEL_NAME") or "gemini-flash-lite-latest"
        return ChatGoogleGenerativeAI(model=model, api_key=api_key)
    except ImportError:
        logger.warning("langchain_google_genai not available")
        return None


def _create_openai(api_key: str) -> object | None:
    try:
        from langchain_openai import ChatOpenAI
        model = os.getenv("OPENAI_MODEL_NAME") or "gpt-4-turbo-preview"
        return ChatOpenAI(model=model, api_key=api_key)
    except ImportError:
        logger.warning("langchain_openai not available")
        return None
```

**Changes from original:**
- Removed `preferred_model` and `prefer_google` params from `create_llm()`
- Removed `_create_fireworks()` function
- Removed `FIREWORKS_API_KEY` from providers list
- Each factory function now reads model from env var (`ANTHROPIC_MODEL_NAME`, `GOOGLE_MODEL_NAME`, `OPENAI_MODEL_NAME`)
- Base URLs are NOT passed explicitly — `ChatAnthropic` natively reads `ANTHROPIC_BASE_URL`/`ANTHROPIC_API_URL`; `ChatOpenAI` natively reads `OPENAI_BASE_URL`
- Each factory falls back to the same defaults as before

- [ ] **Step 3: Verify file syntax**

Run: `python3 -c "import ast; ast.parse(open('packages/a2a-protocol/src/a2a_protocol/llm.py').read()); print('OK')"`

Expected: `OK`

- [ ] **Step 4: Commit**

```bash
git add packages/a2a-protocol/src/a2a_protocol/llm.py
git commit -m "refactor(llm): consolidate providers to 3 API-standard families, add model name env vars"
```

---

### Task 2: Remove fireworks optional dependency

**Files:**
- Modify: `packages/a2a-protocol/pyproject.toml:25`

- [ ] **Step 1: Remove `fireworks` optional dep**

Edit `packages/a2a-protocol/pyproject.toml` — remove line `fireworks = ["langchain-fireworks"]` from `[project.optional-dependencies]`.

- [ ] **Step 2: Commit**

```bash
git add packages/a2a-protocol/pyproject.toml
git commit -m "chore(deps): remove langchain-fireworks optional dependency"
```

---

### Task 3: Update `.env.example`

**Files:**
- Modify: `.env.example` (entire file)

- [ ] **Step 1: Read current file**

Run: `cat .env.example`

- [ ] **Step 2: Replace `.env.example` content**

```env
# ──────────────────────────────────────────────
# LLM — Provider Selection
# ──────────────────────────────────────────────
# La factory usa il PRIMO provider con API key settata, in quest'ordine:
#   1. Anthropic (ANTHROPIC_API_KEY)
#   2. Google    (GOOGLE_API_KEY)
#   3. OpenAI    (OPENAI_API_KEY)
#
# Imposta UNA SOLA chiave alla volta per controllare quale provider usare.

# ── Anthropic (Claude) ─────────────────────────
# https://console.anthropic.com/
ANTHROPIC_API_KEY=
ANTHROPIC_MODEL_NAME=claude-3-5-sonnet-20241022
ANTHROPIC_BASE_URL=https://api.anthropic.com

# ── Google (Gemini) ────────────────────────────
# https://aistudio.google.com/app/apikey
# Google NON supporta base_url custom.
GOOGLE_API_KEY=
GOOGLE_MODEL_NAME=gemini-flash-lite-latest

# ── OpenAI / Compatibili (OpenAI, Fireworks, Groq, Together, Ollama, vLLM) ──
# https://platform.openai.com/api-keys
# Per provider OpenAI-compatibili, cambia BASE_URL e MODEL_NAME.
OPENAI_API_KEY=
OPENAI_MODEL_NAME=gpt-4-turbo-preview
OPENAI_BASE_URL=https://api.openai.com/v1

#   Esempio: Fireworks AI
#   OPENAI_API_KEY=fw_3aBcDeFgHiJkLmNoPqRsTuVwXyZ
#   OPENAI_BASE_URL=https://api.fireworks.ai/inference/v1
#   OPENAI_MODEL_NAME=accounts/fireworks/models/llama-v3p1-70b-instruct

#   Esempio: Groq
#   OPENAI_API_KEY=gsk_...
#   OPENAI_BASE_URL=https://api.groq.com/openai/v1
#   OPENAI_MODEL_NAME=llama-3.3-70b-versatile

#   Esempio: Ollama (locale)
#   OPENAI_API_KEY=ollama          # Ollama ignora la key, ma va settata
#   OPENAI_BASE_URL=http://localhost:11434/v1
#   OPENAI_MODEL_NAME=llama3.2

# WebSocket JWT Secret (condiviso tra frontend e chat-orchestrator)
# Genera con: openssl rand -hex 16
WS_JWT_SECRET=change-this-secret

# NextAuth Secret (usato per firmare i JWT di sessione)
# Genera con: openssl rand -hex 32
AUTH_SECRET=change-this-secret

# A2A Basic Auth per comunicazione inter-agent
A2A_BASIC_AUTH_USERNAME=a2a
A2A_BASIC_AUTH_PASSWORD=change-this-secret
```

- [ ] **Step 3: Commit**

```bash
git add .env.example
git commit -m "docs(env): add LLM model name and base URL env vars, remove FIREWORKS_API_KEY"
```

---

### Task 4: Update `AGENTS.md` configuration section

**Files:**
- Modify: `AGENTS.md` — section 8 "Configuration"

- [ ] **Step 1: Read current AGENTS.md section 8**

Run: grep for "## 8. Configuration" in AGENTS.md

- [ ] **Step 2: Replace the LLM provider section in AGENTS.md**

Replace lines from the "Shared" table start through the Homily Agent table end with:

```markdown
## 8. Configuration

All agents are configured via environment variables. See `.env.example` for a template.

### LLM Provider Selection

La factory in `packages/a2a-protocol/src/a2a_protocol/llm.py` seleziona il provider in base alla **prima API key trovata** nell'ordine: `ANTHROPIC_API_KEY` → `GOOGLE_API_KEY` → `OPENAI_API_KEY`. Solo un provider viene attivato per sessione.

| Per usare... | Setta | Lascia vuoto |
|---|---|---|
| **Claude (Anthropic)** | `ANTHROPIC_API_KEY` | `GOOGLE_API_KEY`, `OPENAI_API_KEY` |
| **Gemini (Google)** | `GOOGLE_API_KEY` | `ANTHROPIC_API_KEY`, `OPENAI_API_KEY` |
| **OpenAI / compatibile** | `OPENAI_API_KEY` | `ANTHROPIC_API_KEY`, `GOOGLE_API_KEY` |

Provider OpenAI-compatibili (Fireworks, Groq, Together, Ollama, vLLM) usano tutti `ChatOpenAI` con `base_url` personalizzata:

| Provider | `OPENAI_BASE_URL` | `OPENAI_MODEL_NAME` |
|---|---|---|
| OpenAI | `https://api.openai.com/v1` | `gpt-4-turbo-preview` |
| Fireworks AI | `https://api.fireworks.ai/inference/v1` | `accounts/fireworks/models/llama-v3p1-70b-instruct` |
| Groq | `https://api.groq.com/openai/v1` | `llama-3.3-70b-versatile` |
| Ollama (locale) | `http://localhost:11434/v1` | `llama3.2` |

### Shared

| Variable | Description |
|----------|-------------|
| `LOG_LEVEL` | Logging level (default: INFO) |
| `LOG_JSON_FORMAT` | Structured JSON logging (default: true) |

### LLM Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `ANTHROPIC_API_KEY` | — | API key per Claude |
| `ANTHROPIC_MODEL_NAME` | `claude-3-5-sonnet-20241022` | Modello Anthropic |
| `ANTHROPIC_BASE_URL` | `https://api.anthropic.com` | Endpoint Anthropic (per proxy/emulatori) |
| `GOOGLE_API_KEY` | — | API key per Gemini |
| `GOOGLE_MODEL_NAME` | `gemini-flash-lite-latest` | Modello Google |
| `OPENAI_API_KEY` | — | API key per OpenAI e provider compatibili |
| `OPENAI_MODEL_NAME` | `gpt-4-turbo-preview` | Modello OpenAI/compatibile |
| `OPENAI_BASE_URL` | `https://api.openai.com/v1` | Endpoint per OpenAI e provider compatibili |

### Chat Orchestrator

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_PATH` | `packages/chat-orchestrator/data/chat_orchestrator.db` | Session database |
| `WS_JWT_SECRET` | — | JWT secret for WebSocket auth |
| `A2A_LITURGY_TRANSPORT` | `stdio` | Transport to liturgy agent |
| `A2A_LITURGY_COMMAND` | `python -m liturgy_agent.main` | Stdio command |
| `A2A_HOMILY_TRANSPORT` | `stdio` | Transport to homily agent |
| `A2A_HOMILY_COMMAND` | `python -m homily_agent.main` | Stdio command |

### Liturgy Agent

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_PATH` | `packages/liturgy-agent/data/liturgy_cache.db` | Cache database |
| `EVANGELIZO_BASE_URL` | `https://evangelizo.org` | Primary scraper source |
| `CACHE_TTL_SECONDS` | `86400` | Cache freshness (24h) |

### Homily Agent

| Variable | Default | Description |
|----------|---------|-------------|
| `PINECONE_API_KEY` | — | Vector DB (production) |
| `PINECONE_INDEX_NAME` | `theological-corpus` | Vector index name |
| `EMBEDDING_MODEL` | `text-embedding-3-large` | Embedding model |
| `RAG_TOP_K` | `5` | Documents to retrieve |
| `RAG_MIN_SIMILARITY` | `0.7` | Minimum similarity threshold |
```

- [ ] **Step 3: Also update Known Issues table (section 10)**

Remove issue #3 (Fireworks `Occasion` mismatch is resolved) and **add new removal note** for `_create_fireworks`:

Replace the table in section 10 with:

```markdown
## 10. Known Issues

| ID | Severity | Issue | File |
|----|----------|-------|------|
| 1 | Critical | `backend/` path references → `packages/` — 17+ files pointed to non-existent directory → **Partially resolved** (2026-05-19): AGENTS.md created, SPECIFICATION.md trimmed, phase reports removed, 12 docs/*.rst fixed, validate_phase2/3 fixed. Remaining: `:doc:`backend/index`` refs in 4 .rst files are Sphinx toctree entries (not filesystem paths). | Multiple |
| 3 | Critical | A2A transport sends to `/a2a` but server listens on `/` — **Resolved** (2026-05-19): changed `HTTPTransport.send()` URL from `{agent_url}/a2a` to `{agent_url}/` to match server route. Also fixed `send_stream` URL. 1 TDD test added. | `a2a-protocol/transport.py:174` |
| 4 | Critical | Blocking `graph.invoke()` inside async method | `homily-agent/main.py:124` |
| 5 | Critical | `_validate_node` discards validation results | `homily-agent/graph.py:117-122` |
| 6 | Important | Cache permanently disabled (`if False and cached`) | `liturgy-agent/cache.py` |
| 7 | Important | Vatican scraper fetches static URL always — **Resolved** (2026-05-19): dead code removed. Only Evangelizo scraper is used. | `liturgy-agent/scrapers.py` |
| 9 | Important | Bible abbreviations inconsistent across agents | `agent.py:259` vs `bible_parser.py:34` |
| 10 | Cleanup | `langchain-fireworks` removed — Fireworks now uses `ChatOpenAI` with `OPENAI_BASE_URL` | `llm.py` |
```

- [ ] **Step 4: Commit**

```bash
git add AGENTS.md
git commit -m "docs(agents): update configuration section with LLM env vars and provider selection"
```

---

### Task 5: Verify chat-orchestrator config is clean

**Files:**
- Check: `packages/chat-orchestrator/src/chat_orchestrator/config.py`

- [ ] **Step 1: Read config.py**

Confirm it calls `create_llm()` with no arguments (which remains valid since we only removed `preferred_model` and `prefer_google`).

The current call is `return create_llm()` — no changes needed. If any call used `prefer_google=True`, remove that argument.

- [ ] **Step 2: Run syntax check**

```bash
python3 -c "import ast; ast.parse(open('packages/chat-orchestrator/src/chat_orchestrator/config.py').read()); print('OK')"
```

Expected: `OK`

- [ ] **Step 3: Commit (if any changes needed)**

Only commit if changes were made. Otherwise skip.

---

### Task 6: Clean up archived/reference docs

**Files:**
- Modify: `docs/plans/refactoring-plan.md` (optional — archived doc but referenced in task output)

- [ ] **Step 1: Check if refactoring-plan.md references the old LLM factory signature**

Run: `grep -n "preferred_model\|prefer_google\|_create_fireworks" docs/plans/refactoring-plan.md`

If there are references and you want to update them (archived doc — optional), do so. Otherwise skip.

- [ ] **Step 2: Commit (if any changes made)**

---

### Task 7: Verify the full test suite

- [ ] **Step 1: Run pytest to check nothing is broken**

```bash
pytest --no-header -q 2>&1 | tail -20
```

Expected: All tests pass (or same failures as before the change — LLM factory had zero test coverage and only mock-dependent tests).

- [ ] **Step 2: Confirm key test files still pass individually**

```bash
pytest packages/liturgy-agent/tests/ --no-header -q 2>&1 | tail -10
pytest packages/chat-orchestrator/tests/ --no-header -q 2>&1 | tail -10
pytest packages/a2a-protocol/tests/ --no-header -q 2>&1 | tail -10
```

Expected: All pass.

- [ ] **Step 3: Final commit of any remaining changes**

```bash
git status  # review
git add -A  # catch any loose files
git commit -m "chore: cleanup stale references and verify tests pass"
```
