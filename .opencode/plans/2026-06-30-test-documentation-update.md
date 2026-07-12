# Test Documentation Update Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Update all test documentation to accurately reflect the current 45-test, 4-layer, 18-file test suite including the `contracts/` package.

**Architecture:** Four documentation files need updates: `contracts/README.md` (full rewrite), `AGENTS.md` §10 (add contracts + fix counts + fix commands), `packages/liturgy-agent/src/liturgy_agent/README.md` (fix stale test file reference), and remove the duplicate `docs/plans/e2e-test-plan.md` (identical to archived copy).

**Tech Stack:** Markdown, pytest, uv, Docker Compose

---

## Current State (verified)

### Actual test files (18 total, not counting `__init__.py` / `conftest.py`)

| Location | Files | Count |
|----------|-------|-------|
| `packages/a2a-protocol/tests/` | `test_llm_factory.py`, `test_standard_a2a.py`, `test_transport_routes.py` | 3 |
| `packages/chat-orchestrator/tests/` | `test_checkpoint_persistence.py`, `test_standard_client.py` | 2 |
| `packages/liturgy-agent/tests/` | `test_agent.py`, `test_integration.py`, `test_main.py` | 3 |
| `packages/homily-agent/tests/` | `test_graph.py`, `rag/test_bible_parser.py`, `rag/test_catechism_parser.py` | 3 |
| `contracts/tests/` | `test_liturgy_contract.py`, `test_homily_contract.py`, `test_liturgy_agent_e2e.py`, `test_homily_agent_e2e.py`, `test_chat_orchestrator_e2e.py`, `test_scenarios_e2e.py` + `conftest.py` | 7 |
| **Total** | | **18** |

### Actual test results (verified with Docker Compose + LLM)

| Suite | Result |
|-------|--------|
| `packages/a2a-protocol/` unit | 28 passed |
| `contracts/` full suite | 45 passed, 0 skipped |
| **Grand total** | **73 passed** |

### Documentation gaps found

| File | Gap |
|------|-----|
| `contracts/README.md` | Missing `homily.adjust_tone`, no run commands, no test layers, no env requirements, no conftest docs, no CI reference, no contract definition tests |
| `AGENTS.md` §10 | `contracts/` entirely missing, wrong test count (14 vs 18), bare `pytest` instead of `uv run pytest`, no 4-layer architecture, no CI workflow |
| `packages/liturgy-agent/src/liturgy_agent/README.md` | References nonexistent `test_cache.py` |
| `docs/plans/e2e-test-plan.md` | Duplicate of `docs/plans/archived/e2e-test-plan.md` (identical), uses `requests` not `httpx`, says 22 tests (actual 45), missing contract tests |

---

## File Structure

| File | Action | Responsibility |
|------|--------|----------------|
| `contracts/README.md` | Rewrite | Single source of truth for contract test execution, layers, env, fixtures |
| `AGENTS.md` §10 (lines 563-601) | Edit | Architecture-level test overview including contracts/ |
| `packages/liturgy-agent/src/liturgy_agent/README.md` (lines 35-46) | Edit | Fix stale test file references |
| `docs/plans/e2e-test-plan.md` | Delete | Remove duplicate (archived copy exists at `docs/plans/archived/e2e-test-plan.md`) |

---

### Task 1: Rewrite `contracts/README.md`

**Files:**
- Modify: `contracts/README.md` (full rewrite, currently 40 lines)

- [ ] **Step 1: Replace the entire file content**

```markdown
# A2A Contract Tests

Consumer-driven contract tests for the A2A (Agent-to-Agent) JSON-RPC 2.0 API.
Verifies that all agents comply with the protocol specification and produce
responses that consumers expect.

## Test Layers

The suite has four layers, each with different infrastructure requirements:

| Layer | Files | Needs agents? | Needs Docker? | Tests run |
|-------|-------|:---:|:---:|-----------|
| **A. Contract definition** | `test_liturgy_contract.py::TestContractCompliance`, `test_homily_contract.py::TestHomilyContractDefinition` | No | No | Validates contract JSON files: required fields, method names, error codes, enum values |
| **B. Live agent** | `test_liturgy_contract.py::TestLiturgyAgentContract`, `test_homily_contract.py::TestHomilyAgentContract` | Yes (ports 8001/8002) | No | Sends `message/send` requests, validates reply against Pydantic models. Skips if agent unreachable |
| **C. E2E** | `test_liturgy_agent_e2e.py`, `test_homily_agent_e2e.py`, `test_chat_orchestrator_e2e.py`, `test_scenarios_e2e.py` | Yes (ports 8000-8002) | Optional | Raw JSON-RPC POSTs + WebSocket flows. `conftest.py` can start Docker Compose automatically |
| **D. Protocol unit** | `packages/a2a-protocol/tests/` | No | No | Mock-handler unit tests of the A2A server, transport, and LLM factory |

## Test File Structure

```
contracts/
├── liturgy-agent-contract.json      # Liturgy agent API spec (3 methods)
├── homily-agent-contract.json       # Homily agent API spec (4 methods)
├── pyproject.toml                   # pytest config, dependencies
└── tests/
    ├── conftest.py                        # Fixtures: .env loader, Docker lifecycle, URL fixtures, MOCK_LITURGICAL_DATA
    ├── test_liturgy_contract.py           # Layer A+B: contract definition + live agent
    ├── test_homily_contract.py            # Layer A+B: contract definition + live agent
    ├── test_liturgy_agent_e2e.py          # Layer C: liturgy agent A2A methods
    ├── test_homily_agent_e2e.py           # Layer C: homily agent A2A methods
    ├── test_chat_orchestrator_e2e.py      # Layer C: WebSocket + chat orchestration
    └── test_scenarios_e2e.py              # Layer C: multi-step user scenarios
```

## Agents Under Test

### Liturgy Agent (port 8001)
- `agent.ping` — Health check
- `liturgy_agent.get_readings` — Fetch liturgical readings for a date
- `liturgy_agent.get_lectionary` — Get ritual lectionary for sacraments

### Homily Agent (port 8002)
- `agent.ping` — Health check
- `homily.generate` — Generate homily from liturgical data
- `homily.refine` — Refine existing homily with new preferences
- `homily.adjust_tone` — Adjust tone of an existing homily

### Chat Orchestrator (port 8000)
- `GET /health` — Health check
- `WS /ws/chat/{session_id}` — WebSocket chat with JWT auth

## Running Tests

```bash
# --- Layer A: Static contract definition tests (no agents needed) ---
cd contracts
uv run pytest tests/test_liturgy_contract.py::TestContractCompliance \
               tests/test_homily_contract.py::TestHomilyContractDefinition -v

# --- Layer A+D: All static + protocol unit tests (no agents needed) ---
cd contracts && uv run pytest tests/test_liturgy_contract.py tests/test_homily_contract.py -v
cd packages/a2a-protocol && uv run pytest -v

# --- Layer A+B+C: Full suite via Docker Compose (auto starts/stops services) ---
cd contracts && uv run pytest tests/ -v

# --- Full suite, services already running ---
cd contracts && uv run pytest tests/ -v --no-docker

# --- Specific agent ---
cd contracts && uv run pytest tests/test_liturgy_agent_e2e.py -v
cd contracts && uv run pytest tests/test_homily_contract.py -v

# --- Skip slow tests ---
cd contracts && uv run pytest tests/ -v -m "not slow"
```

## Environment Requirements

The test suite loads `.env` automatically via `conftest.py:_load_env()`.
The following variables must be set for live/E2E tests:

| Variable | Required for | Source |
|----------|-------------|--------|
| `WS_JWT_SECRET` | WebSocket tests (chat orchestrator) | `.env` (auto-loaded by conftest) |
| `A2A_BASIC_AUTH_USERNAME` | A2A HTTP requests | `.env` — **must be empty to run tests** (test helpers don't send auth headers) |
| `A2A_BASIC_AUTH_PASSWORD` | A2A HTTP requests | `.env` — **must be empty to run tests** |
| `OPENAI_API_KEY` | Homily generation (LLM) | `.env` — needed for `homily.generate`/`refine`/`adjust_tone` |
| `A2A_LITURGY_URL` | Liturgy agent URL | Defaults to `http://localhost:8001` |
| `A2A_HOMILY_URL` | Homily agent URL | Defaults to `http://localhost:8002` |

> **Note on Basic Auth:** The test helpers (`make_message_send`, `httpx.post`) do not
> send `Authorization` headers. If `A2A_BASIC_AUTH_*` are set, all live/E2E tests will
> 401. To run the full suite, start Docker with auth disabled:
> ```bash
> A2A_BASIC_AUTH_USERNAME= A2A_BASIC_AUTH_PASSWORD= docker compose up -d --build liturgy-agent homily-agent chat-orchestrator
> ```

## Fixtures (conftest.py)

| Fixture | Scope | Description |
|---------|-------|-------------|
| `docker_compose` | session | Starts/stops Docker Compose (skipped with `--no-docker`) |
| `_ensure_docker` | module | Depends on `docker_compose` |
| `liturgy_url` | function | Returns `http://localhost:8001` |
| `homily_url` | function | Returns `http://localhost:8002` |
| `chat_url` | function | Returns `http://localhost:8000` |
| `MOCK_LITURGICAL_DATA` | — | Module-level dict with sample readings for homily tests |

## CI

Contract tests run on push/PR to `main` via `.github/workflows/contract-tests.yml`.
The workflow installs all packages, starts liturgy + homily agents with mock LLM,
waits for health, then runs `uv run pytest tests/ -v --junit-xml=test-results.xml`.

## Test Count Summary

| File | Tests | Layer | What it covers |
|------|-------|-------|----------------|
| `test_liturgy_contract.py` | 9 | A+B | Contract definition (5) + live agent ping/readings/lectionary (4) |
| `test_homily_contract.py` | 9 | A+B | Contract definition (2) + live agent ping/generate/refine/tone (5) + error handling (2) |
| `test_liturgy_agent_e2e.py` | 10 | C | Ping, readings (happy + errors), lectionary, cache hit |
| `test_homily_agent_e2e.py` | 10 | C | Ping, generate (all occasions), refine, adjust tone, errors |
| `test_chat_orchestrator_e2e.py` | 4 | C | Health, WebSocket chat, multi-message, homily flow |
| `test_scenarios_e2e.py` | 3 | C | Liturgy→homily full flow, wedding flow, error recovery |
| **Total** | **45** | | |

## Related

- Protocol definition: `packages/a2a-protocol/`
- Agent implementations: `packages/liturgy-agent/`, `packages/homily-agent/`
- Consumer: `packages/chat-orchestrator/`
- Architecture guide: `AGENTS.md` §10 (Testing)
```

- [ ] **Step 2: Verify the file was written correctly**

Run: `head -5 contracts/README.md`
Expected output starts with `# A2A Contract Tests`

- [ ] **Step 3: Commit**

```bash
git add contracts/README.md
git commit -m "docs: rewrite contracts/README.md with test layers, run commands, env requirements"
```

---

### Task 2: Update `AGENTS.md` §10 Testing

**Files:**
- Modify: `AGENTS.md` lines 563-601 (§10 Testing section)

- [ ] **Step 1: Replace the Test Locations table (lines 565-573)**

Replace this block:
```
### Test Locations

| Agent | Path | Test Count |
|-------|------|------------|
| A2A Protocol | `packages/a2a-protocol/tests/` | 3 files |
| Chat Orchestrator | `packages/chat-orchestrator/tests/` | 3 files |
| Liturgy Agent | `packages/liturgy-agent/tests/` | 4 files |
| Homily Agent | `packages/homily-agent/tests/` | 4 files (1 subdirectory) |
| **Total** | | **14 test files** |
```

With:
```
### Test Locations

| Location | Path | Files | Layer |
|----------|------|:-----:|-------|
| A2A Protocol | `packages/a2a-protocol/tests/` | 3 | Unit |
| Chat Orchestrator | `packages/chat-orchestrator/tests/` | 2 | Unit |
| Liturgy Agent | `packages/liturgy-agent/tests/` | 3 | Unit |
| Homily Agent | `packages/homily-agent/tests/` | 3 | Unit |
| Contracts | `contracts/tests/` | 7 | Static + Live + E2E |
| **Total** | | **18 test files** | |
```

- [ ] **Step 2: Replace the Running Tests section (lines 575-592)**

Replace this block:
```
### Running Tests

```bash
# All tests
pytest

# Specific agent
pytest packages/liturgy-agent/tests/

# With coverage
pytest --cov=packages.liturgy-agent.src.liturgy_agent packages/liturgy-agent/tests/

# Specific module
pytest packages/a2a-protocol/tests/test_transport_routes.py -v

# Skip Docker-dependent tests
pytest -m "not docker"
```
```

With:
```
### Running Tests

```bash
# --- Package unit tests ---
cd packages/a2a-protocol && uv run pytest -v
cd packages/liturgy-agent && uv run python -m pytest -v
cd packages/homily-agent && uv run python -m pytest -v
cd packages/chat-orchestrator && uv run pytest -v

# --- Contract tests (static definition, no agents needed) ---
cd contracts && uv run pytest tests/test_liturgy_contract.py::TestContractCompliance \
               tests/test_homily_contract.py::TestHomilyContractDefinition -v

# --- Contract tests (full suite via Docker Compose) ---
cd contracts && uv run pytest tests/ -v

# --- Contract tests (services already running) ---
cd contracts && uv run pytest tests/ -v --no-docker

# --- With coverage ---
cd packages/liturgy-agent && uv run python -m pytest --cov=src/liturgy_agent tests/

# --- Specific module ---
cd packages/a2a-protocol && uv run pytest tests/test_transport_routes.py -v
```

> **Note:** Contract live/E2E tests require running agents. Start them via
> `docker compose up -d --build liturgy-agent homily-agent chat-orchestrator`
> or let `conftest.py` manage Docker Compose automatically. See
> [`contracts/README.md`](contracts/README.md) for env requirements.
```

- [ ] **Step 3: Replace the Test Categories table (lines 594-601)**

Replace this block:
```
### Test Categories

| Type | Scope | Notes |
|------|-------|-------|
| Unit | Individual modules, isolated | Fast, no external dependencies |
| Integration | Agent boundaries, A2A communication | Requires agent servers running |
| E2E | Full user → chat → agent flows | Requires Docker Compose |
```

With:
```
### Test Categories

| Type | Scope | Location | Notes |
|------|-------|----------|-------|
| Unit | Individual modules, isolated | `packages/*/tests/` | Fast, no external dependencies, uses mocks |
| Contract definition | Static JSON contract validation | `contracts/tests/test_*_contract.py` | No agents needed; validates fields, methods, error codes |
| Live agent | A2A message/send against running agent | `contracts/tests/test_*_contract.py` | Requires agents on ports 8001/8002; skips if unreachable |
| E2E | Full user → chat → agent flows | `contracts/tests/test_*_e2e.py` | Requires Docker Compose or `--no-docker` with running services |

### CI

Contract tests run on push/PR to `main` via
[`.github/workflows/contract-tests.yml`](.github/workflows/contract-tests.yml).
See [`contracts/README.md`](contracts/README.md) for full details.
```

- [ ] **Step 4: Verify the section reads correctly**

Run: `grep -n "contracts\|18 test\|uv run\|Contract definition\|Live agent\|contract-tests.yml" AGENTS.md`
Expected: multiple matches in the §10 range showing the new content.

- [ ] **Step 5: Commit**

```bash
git add AGENTS.md
git commit -m "docs: update AGENTS.md §10 with contracts/ tests, correct counts, uv run commands"
```

---

### Task 3: Fix stale test reference in liturgy-agent README

**Files:**
- Modify: `packages/liturgy-agent/src/liturgy_agent/README.md` lines 35-46

- [ ] **Step 1: Replace the Testing section (lines 35-46)**

Replace this block:
```
## Testing

```bash
# All tests
pytest packages/liturgy-agent/tests/

# Specific module
pytest packages/liturgy-agent/tests/test_cache.py

# With coverage
pytest --cov=packages.liturgy-agent.src.liturgy_agent packages/liturgy-agent/tests/
```
```

With:
```
## Testing

```bash
# All tests
cd packages/liturgy-agent && uv run python -m pytest -v

# Specific module
cd packages/liturgy-agent && uv run python -m pytest tests/test_agent.py -v

# With coverage
cd packages/liturgy-agent && uv run python -m pytest --cov=src/liturgy_agent tests/
```

Test files: `test_agent.py`, `test_integration.py`, `test_main.py`.
```

- [ ] **Step 2: Commit**

```bash
git add packages/liturgy-agent/src/liturgy_agent/README.md
git commit -m "docs: fix stale test_cache.py reference in liturgy-agent README"
```

---

### Task 4: Remove duplicate e2e-test-plan.md

**Files:**
- Delete: `docs/plans/e2e-test-plan.md` (identical to `docs/plans/archived/e2e-test-plan.md`)

- [ ] **Step 1: Verify the files are still identical**

Run: `diff docs/plans/e2e-test-plan.md docs/plans/archived/e2e-test-plan.md`
Expected: no output (files identical).

- [ ] **Step 2: Delete the active copy**

Run: `rm docs/plans/e2e-test-plan.md`

- [ ] **Step 3: Verify deletion**

Run: `ls docs/plans/e2e-test-plan.md 2>&1`
Expected: "No such file or directory"

- [ ] **Step 4: Commit**

```bash
git add -A docs/plans/e2e-test-plan.md
git commit -m "docs: remove duplicate e2e-test-plan.md (archived copy exists)"
```

---

## Verification

After all 4 tasks are complete:

- [ ] **Step 1: Verify no stale references remain**

Run: `grep -rn "test_cache\|14 test files\|pytest packages" --include="*.md" .`
Expected: no matches (or only matches in `docs/plans/archived/` which is historical).

- [ ] **Step 2: Verify contracts/README.md has key sections**

Run: `grep -c "## " contracts/README.md`
Expected: at least 8 (Test Layers, Test File Structure, Agents Under Test, Running Tests, Environment Requirements, Fixtures, CI, Test Count Summary, Related).

- [ ] **Step 3: Verify AGENTS.md has contracts/ references**

Run: `grep -c "contracts" AGENTS.md`
Expected: at least 5 (more than the 1 reference that existed before).
