# Comprehensive Codebase Analysis

## Prete-a-porter — 4 packages in `packages/`

Analysis performed using: python-code-style, python-design-patterns, python-error-handling, python-packaging skills.

---

## Structure Overview

```
packages/
├── a2a-protocol/src/a2a_protocol/       — Libreria A2A (protocol, transport, client, server)
├── chat-orchestrator/src/chat_orchestrator/ — Orchestrator WebSocket+agenti
├── homily-agent/src/homily_agent/        — Agente generazione omelie
└── liturgy-agent/src/liturgy_agent/      — Agente dati liturgici
```

---

## 🔴 Critical Issues

### 1. `chat-orchestrator/main.py` — God File (696 lines)

Single file with **7 distinct responsibilities**:

| Responsibility | Lines | Key Function |
|---|---|---|
| Tool definitions | 49-110 | `get_current_date`, `calculate_date` |
| LLM initialization | 212-263 | `_get_llm` (52 lines) |
| Graph construction | 266-504 | `agent_node`, `tools_node`, `create_graph` |
| Graph node logic | 266-432 | `agent_node` (78 lines), `tools_node` (74 lines) |
| WebSocket endpoint | 529-696 | `chat_websocket` (149 lines) |
| HTTP health endpoint | 518-527 | `health` |
| Application startup | 699-714 | `start`, CORS, middleware |
| System prompt | 120-148 | `SYSTEM_PROMPT` |

**`chat_websocket` (149 lines)** handles: connection acceptance, graph initialization, message receive loop, graph invocation via `graph.ainvoke()`, AI message extraction, response formatting, error handling (3 nested try/except levels), and connection lifecycle.

**`agent_node` (78 lines)** handles: LLM initialization, tool binding, system prompt prepend, LLM invocation, logging, error wrapping in `AgentGraphException`.

**`tools_node` (74 lines)** handles: tool lookup, tool invocation via `func.invoke()`, error handling per tool, `ToolMessage` construction, logging with session_id.

### 2. `asyncio.run()` Anti-Pattern in `chat-orchestrator/tools.py`

**4 sync `@tool` functions** use `asyncio.run()` to bridge sync→async:

```python
@tool
def get_liturgical_readings(occasion: str, date: Optional[str] = None) -> Dict[str, Any]:
    try:
        result = asyncio.run(request_liturgical_data(occasion, date))  # ← BAD
        return result
```

**Problems:**
- Creates a new event loop on every single invocation
- **Crashes** when called from an already-running async context (e.g., LangGraph ReAct loop, WebSocket handler)
- Makes the tools unusable from async code paths
- The tools should be `async def` to match LangChain's async tool model

### 3. `a2a-protocol` Version Mismatch

| Source | Version |
|---|---|
| `packages/a2a-protocol/pyproject.toml` | `0.1.0` |
| `packages/a2a-protocol/src/a2a_protocol/__init__.py` | `1.0.0` |

This causes confusion for consumers and tooling.

### 4. All 4 Packages Missing Authors/License

Required for PyPI publication. Every `pyproject.toml` is missing:
- `authors = [{...}]`
- `license = {text = "..."}`
- `classifiers = [...]`
- `keywords = [...]`

### 5. `a2a-protocol` — Duplicate Dev Dependency Groups

Two different `dev` groups with **conflicting version pins**:

```toml
# [project.optional-dependencies] — line 12
dev = ["pytest>=8.0.0", "pytest-asyncio>=0.23.0", "pytest-cov>=4.1.0"]

# [dependency-groups] — line 59 (uv override)
dev = ["pytest>=9.0.2", "pytest-asyncio>=1.3.0", "pytest-cov>=7.0.0"]
```

`pytest>=9.0.2` doesn't exist as of 2026 — this will break installation.

### 6. Custom Exception Hierarchy Not Used Across Packages

`chat-orchestrator/exceptions.py` has **19 exception classes** in a 3-level hierarchy:
```
PreteAPorterException → LLMException, DatabaseException, WebSocketException, 
                        ValidationException, ToolException, AgentException, 
                        A2AException, ExternalServiceException
```

But:
- `liturgy-agent` and `homily-agent` **don't use them at all**
- `chat-orchestrator/tools.py` wraps A2A errors in `RuntimeError` instead of `A2ACommunicationException`
- `a2a-protocol/server.py` has zero custom exceptions — returns `str(e)` raw to clients

---

## 🟠 Medium Issues

### 7. `_get_llm()` Duplicated in 2 Packages

Nearly identical logic in:
- `chat-orchestrator/src/chat_orchestrator/main.py:212-263` (52 lines)
- `liturgy-agent/src/liturgy_agent/main.py:57-115` (59 lines)

Both iterate: `TEST_MODE` → `ANTHROPIC_API_KEY` → `GOOGLE_API_KEY` → `FIREWORKS_API_KEY`. The liturgy version also checks `OPENAI_API_KEY`. Should be extracted to a shared `LLMFactory`.

### 8. `A2AServer.create_fastapi_app()` — God Function (187 lines)

Defines 5 route handler closures inline:
- `POST /` (handles custom A2A + Google A2A routing)
- `POST /message:send` 
- `GET /tasks/{task_id}`
- `GET /tasks`
- `GET /.well-known/agent-card.json`
- `GET /health`

Plus 2 inline helper functions (`_make_jsonrpc_response`, `_make_jsonrpc_error`) and JSON-RPC 2.0 routing logic. Cannot be independently tested.

### 9. `a2a-protocol/server.py` — Raw Error Leakage

Every endpoint handler returns `str(e)` directly to clients:
```python
except Exception as e:
    return Response(content=json.dumps({"error": str(e)}), ...)
```

Leaks internal details: file paths, module names, stack traces. Should return sanitized error codes.

### 10. Liturgy Agent Cache Permanently Disabled

`packages/liturgy-agent/src/liturgy_agent/main.py:193`:
```python
if False and cached:  # ← Always False
```

Cache is **written** to (line 213) but **never read**. Every request hits the web scraper, making the cache SQLite file write-only dead code.

### 11. `[tool.uv.sources]` Locks to uv

All 3 agent packages use `[tool.uv.sources]` for local `a2a-protocol` dependency:
```toml
[tool.uv.sources]
a2a-protocol = { path = "../a2a-protocol", editable = true }
```

`pip install .` and standard Python tooling **cannot resolve** this dependency. Works only with `uv`.

### 12. `numpy<2` Without Lower Bound

`packages/homily-agent/pyproject.toml:11`:
```toml
"numpy<2",
```

This will accept `numpy==1.0.0` (released 2006). Should be `numpy>=1.24.0,<2` or similar.

### 13. Homily Agent — Copy-Paste Methods

`_generate_homily` (43 lines), `_refine_homily` (38 lines), and `_adjust_tone` (36 lines) in `packages/homily-agent/src/homily_agent/main.py` share >80% identical code:
1. Parse `liturgical_data` and `preferences` from params
2. Create `HomilyAgentState` 
3. Invoke graph
4. Extract `homily_state.generated_homily`
5. Return formatted response

### 14. Functions Exceeding 50-Line Threshold

| File | Function | Lines | Over by |
|---|---|---|---|
| `chat-orchestrator/main.py` | `chat_websocket` | 149 | +99 |
| `a2a-protocol/server.py` | `create_fastapi_app` | 187 | +137 |
| `chat-orchestrator/main.py` | `agent_node` | 78 | +28 |
| `chat-orchestrator/main.py` | `tools_node` | 74 | +24 |
| `chat-orchestrator/tools.py` | `request_liturgical_data` | 65 | +15 |
| `chat-orchestrator/main.py` | `_get_llm` | 52 | +2 |
| `a2a-protocol/server.py` | `_handle_send_message` | 55 | +5 |
| `a2a-protocol/server.py` | `_generate_agent_card` | 52 | +2 |
| `liturgy-agent/main.py` | `_handle_get_readings` | 112 | +62 |
| `liturgy-agent/main.py` | `_get_llm` | 59 | +9 |
| `liturgy-agent/agent.py` | `_build_reading_from_scraped` | 84 | +34 |
| `liturgy-agent/agent.py` | `_normalize_bible_reference` | 78 | +28 |
| `liturgy-agent/agent.py` | `get_daily_readings` | 56 | +6 |

### 15. Missing `agent.ping` in Homily Agent Handler

The homily agent's `__call__` method doesn't handle `agent.ping` — it falls through to the "Unknown method" error. The a2a-protocol server now handles it at the server level (added in this branch), but the handler doesn't know about it.

---

## 🟢 Minor Issues

### 16. `Evangelize_Scraper` — Naming Convention Violation

`packages/liturgy-agent/src/liturgy_agent/scrapers.py:40`:
```python
class Evangelize_Scraper:  # ← Underscore between words
```

Should be `EvangelizeScraper` (PascalCase). All other classes in the file (`VaticanScraper`, `ScraperError`) are correct.

### 17. Missing `__version__` in `__init__.py`

| Package | Has `__version__` | Value matches pyproject.toml? |
|---|---|---|
| `a2a-protocol` | ✅ Yes | ❌ `1.0.0` vs `0.1.0` |
| `liturgy-agent` | ✅ Yes | ✅ `0.1.0` |
| `chat-orchestrator` | ❌ **No** | — |
| `homily-agent` | ❌ **No** | — |

### 18. No Linter/Formatter Configuration

Zero `[tool.ruff]`, `[tool.mypy]`, `[tool.black]`, or `[tool.isort]` sections in any `pyproject.toml`. No enforced code style consistency.

### 19. Global Mutable State

`chat-orchestrator/tools.py`:
```python
_liturgy_client = None   # Module-level global
_homily_client = None    # Module-level global
```

`chat-orchestrator/main.py`:
```python
_graph = None               # Module-level global
_checkpointer_context = None  # Module-level global
```

State leaks between tests, no thread safety, no clean shutdown.

### 20. `_parse_intent` Uses Keyword Matching

`packages/liturgy-agent/src/liturgy_agent/agent.py:498-526`:
```python
async def _parse_intent(query: str, llm: Any) -> list[str]:
    if "marriage" in query_lower or "wedding" in query_lower:
        return ["occasion"]
    elif "baptism" in query_lower:
        return ["occasion"]
    # ...
```

Uses simple keyword matching instead of LLM-based intent parsing, despite having an `llm` parameter available. Limited to English/Italian keywords.

### 21. `LiturgicalMetadata.sunday_or_weekday` Type Drift

| Package | Type |
|---|---|
| `liturgy-agent/state.py:43` | `Literal["Sunday", "Weekday"]` ✅ |
| `homily-agent/state.py:43` | `str` ❌ (generic) |

### 22. Unused Imports After main.py Split

`graph.py` importava `BaseMessage`, `AIMessage`, `HumanMessage` dal vecchio `main.py`. Dopo lo split, nessuno di questi è usato in `graph.py` (sono usati in `routes.py`).

Fix applicato: rimossi import inutilizzati.

### 23. DB Path Rotation After Split

`create_graph()` calcolava il path del DB SQLite con `Path(__file__).parent.parent`. Dopo lo spostamento di `main.py` da `src/` a `src/chat_orchestrator/`, il path risultava spostato di un livello.

Fix applicato: ora usa `/app/data/chat_orchestrator.db` come default (absolute path, corrisponde al volume mount di Docker).

### 24. Volume Mount DB vs Default Path

In Docker Compose, i volumi montano:
- `./data/chat_orchestrator.db:/app/data/chat_orchestrator.db`
- `./data/liturgy_cache.db:/app/data/liturgy_cache.db`

Ma i default a runtime potrebbero non corrispondere. Va verificato che `DATABASE_PATH` sia impostato correttamente negli env di ogni servizio.

---

## Async/Await Audit

L'uso estensivo di `async/await` è stato introdotto per risolvere il crash di `asyncio.run()` dentro un event loop già attivo. Ecco l'analisi puntuale di dove è necessario e dove no.

### Obbligatoriamente async (I/O reale)

| Funzione | Motivo | Alternativa sync? |
|---|---|---|
| `chat_websocket()` | WebSocket FastAPI | ❌ No |
| `correlation_id_middleware()` | FastAPI middleware | ❌ No |
| `request_liturgical_data()` | HTTP via `httpx` ad agent esterno | ❌ No |
| `request_homily_generation()` | HTTP via `httpx` ad agent esterno | ❌ No |
| `request_homily_refinement()` | HTTP via `httpx` ad agent esterno | ❌ No |
| `get_lectionary_options()` | HTTP via `httpx` ad agent esterno | ❌ No |
| `create_graph()`/`get_graph()` | AsyncSqliteSaver (checkpointer) | ❌ No |
| `a2a_protocol.client.call()` | HTTP via `httpx` | ❌ No |
| `a2a_protocol.transport.send()` | HTTP via `httpx` | ❌ No |
| `serve_http()` | Uvicorn async server loop | ❌ No |
| `_handle_get_readings()` | Chiama `fetch_liturgical_data()` (I/O) | ❌ No |
| `__call__()` in agent handlers | A2A protocol async handler signature | ❌ No |

### Async per convenienza (potrebbero essere sync)

| Funzione | Perché async? | Si può rendere sync? |
|---|---|---|
| `health()` endpoint | Chiamata da FastAPI, ma non fa I/O | ✅ Sì |
| `_handle_get_lectionary()` | Legge da file JSON, ma chiamata da async | ⚠️ Sì, ma va cambiato il chiamante |
| `_generate_homily()` | Chiama `self.graph.invoke()` sync | ✅ Sì |
| `_refine_homily()` | Stesso pattern | ✅ Sì |
| `_adjust_tone()` | Stesso pattern | ✅ Sì |
| `agent_node()` | Usa `llm.ainvoke()` invece di `invoke()` | ✅ Sì, ma serve per async tools |
| `tools_node()` | Usa `func.ainvoke()` per tool async | ❌ No, tool sono async |

### Altre considerazioni

- **FastAPI supporta `async def` e `def` indifferentemente**: i route handler sync vengono eseguiti in un thread pool.
- **LangGraph supporta nodi sync e async misti** in `ainvoke()`, ma non in `invoke()`.
- **I 4 `@tool` devono essere async** perché chiamano funzioni HTTP. Non c'è alternativa.
- **Se `tools_node` è async, anche `agent_node` deve poter essere async** (LangGraph li tratta separatamente ma è più pulito averli coerenti).
- **Il mock per test** deve supportare `.ainvoke()` oltre a `.invoke()`.

**Conclusione**: le uniche funzioni che si potrebbero rendere sync senza impatto sono `health()`, `_handle_get_lectionary()`, e i 3 metodi di generazione omelia (`_generate_homily`, `_refine_homily`, `_adjust_tone`). Tutto il resto è async per necessità (I/O reale o interfaccia imposta dal framework).

| Package | Type |
|---|---|
| `liturgy-agent/state.py:43` | `Literal["Sunday", "Weekday"]` ✅ |
| `homily-agent/state.py:43` | `str` ❌ (generic) |

---

## ✅ Strengths

### Exception Hierarchy (chat-orchestrator/exceptions.py)

**19 classes, 3 levels deep** with consistent patterns:
```python
class PreteAPorterException(Exception):
    def __init__(self, message: str, ..., error_code: str, details: dict | None = None):
        self.error_code = error_code
        self.details = details
        super().__init__(message)
```

- Each subclass has a unique `error_code` (e.g., `"LLM_NOT_CONFIGURED"`, `"TOOL_NOT_FOUND"`)
- Every exception includes Italian user message in `user_message_it`
- Error handlers route by exception type with correct HTTP status codes (400, 429, 503)

### Partial Failure Handling (scrapers.py)

Best pattern in the codebase:
```python
results = await asyncio.gather(*tasks, return_exceptions=True)
for i, result in enumerate(results):
    if isinstance(result, Exception):
        logger.warning(f"Scraper {i} failed: {result}")
        continue
    # Process result
```

Isolates failures per source, logs independently, other sources still contribute.

### Docstrings

Google-style docstrings on nearly every public function/class across all 4 packages. Detailed Args/Returns/Raises sections with examples.

### Pytest/Coverage Configuration

All 4 packages share identical high-quality config:
```toml
[tool.pytest.ini_options]
addopts = ["--strict-markers", "--strict-config", "--verbose"]
asyncio_mode = "auto"

[tool.coverage.run]
source = ["src"]
branch = true
```

### Package Structure

All 4 packages now use the clean `src/` layout with consistent `[tool.setuptools.packages.find] where = ["src"]`.

---

## Cross-Cutting Recommendations

### Priority 1: Structural
1. Split `chat-orchestrator/main.py` into modules: `routes.py`, `graph.py`, `tools.py`, `config.py`
2. Extract duplicated `_get_llm()` into shared `LLMFactory`
3. Fix `asyncio.run()` by making tools `async def`
4. Split `A2AServer.create_fastapi_app()` into smaller methods
5. Remove copy-paste in homily agent's `_generate_*` methods
6. Add sanitized error codes to a2a-protocol/server.py

### Priority 2: Error Handling
7. Propagate custom exceptions to liturgy/homily agents
8. Fix liturgy agent cache (`if False and cached`)
9. Add exception chaining (`from e`) in liturgy-agent and scrapers

### Priority 3: Packaging
10. Fix a2a-protocol version mismatch
11. Add authors/license to all 4 packages
12. Remove duplicate dev dep groups in a2a-protocol
13. Add `__version__` to chat-orchestrator and homily-agent `__init__.py`
14. Add `[tool.ruff]` and `[tool.mypy]` to all packages
15. Fix `numpy<2` lower bound

### Priority 4: Async cleanup
16. Convert `health()` endpoints to sync where possible
17. Convert `_handle_get_lectionary()` to sync
18. Standardize homily-agent `_generate_*` methods (extract `_invoke_graph`)
19. Verify DB path defaults match Docker volume mounts in docker-compose.yml
