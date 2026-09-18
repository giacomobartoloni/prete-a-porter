# Verification levels

How each module was actually tested for the client-shell migrations (OpenWebUI and
LibreChat), and what each level can and cannot prove.

> **Not to be confused with [`testing.rst`](testing.rst).** That document describes an
> intended strategy and is substantially aspirational: it names Cypress, Jest,
> `freezegun`, `pytest-timeout`, and a `conftest.py` that **do not exist in this
> repository**. The frontend uses Playwright. Treat `testing.rst` as a proposal; treat
> this file as the record of what was executed.

## The five levels

Each level answers a different question. Skipping a level leaves a class of defect
undetectable — the table at the end shows which.

| Level | Question it answers | Mechanism | Speed |
|---|---|---|---|
| **0. Library contract** | Does the third-party API behave as assumed? | one-off scripts against the installed packages | seconds |
| **1. Unit** | Does this function do what its name says? | `pytest`, no containers, no network | ~0.9 s for 203 tests |
| **2. Container** | Does it run where it will actually run? | `docker compose`, `docker exec`, `curl` against the built image | minutes |
| **3. Integration, stubbed model** | Does the chain hold without a model? | a local OpenAI-compatible stub | ~10 s |
| **4. End-to-end, real model** | Does the product work? | `curl` against the running stack | ~30 s per turn |

### Level 0 — Library contract

Third-party behaviour that the code depends on but cannot control. Verified by running
the installed library, never by reading its documentation.

```bash
cd packages/chat-orchestrator && uv run python - <<'EOF'
# LangGraph's input contract
from langgraph.graph import StateGraph, END, MessagesState
# ... see the probes recorded in the activity log
EOF
```

Established this way:

- LangGraph accepts a **missing declared channel** (it becomes `None`) and **ignores
  unknown keys** in the invoke payload.
- A graph compiled without a checkpointer accepts `config` with **no `thread_id`**; a
  graph compiled **with** one raises
  `ValueError: Checkpointer requires one or more of the following 'configurable' keys`.
- `astream(..., stream_mode="messages")` yields `(message_chunk, metadata)` tuples
  carrying `langgraph_node`.
- `AIMessageChunk.tool_call_chunks` is `[]`, not `None` — so the filter must test
  **truthiness**, not `is not None`.
- Instrumenting `StreamMessagesHandler._emit` disproved a claim this work had already
  written down: the full `AIMessage` re-emitted by `on_llm_end` carries the *same*
  message id as the deltas and **is** suppressed by the built-in dedupe.
- `a2a_protocol.llm.create_llm` under `TEST_MODE=true` returns an `AsyncMock` whose
  `bind_tools()` yields a **coroutine**, so it cannot drive `agent_node`.

**Proves:** the assumptions are true for the installed versions.
**Cannot prove:** anything about this repository's own logic.

### Level 1 — Unit

```bash
cd packages/chat-orchestrator && uv run pytest tests/ -v
cd contracts && uv run pytest tests/ -v --no-docker
```

203 tests in `packages/chat-orchestrator/tests/`, plus the contract suite.

| Test file | Tests | Module under test | Level |
|---|---:|---|---|
| `test_api_schemas.py` | 8 | `api/schemas.py` | 1 |
| `test_api_messages.py` | 23 | `api/messages.py` (conversion + token filter) | 1 |
| `test_api_sse_frames.py` | 12 | `api/sse.py` | 1 |
| `test_api_auth.py` | 9 | `api/auth.py` | 1 |
| `test_api_identity.py` | 15 | `api/identity.py` (both header families) | 1 |
| `test_api_tasks.py` | 16 | `api/tasks.py` (classification) | 1 |
| `test_api_v1.py` | 20 | `api/v1.py` (models, buffered, auth, quota, boundary logs) | 1 |
| `test_api_timeout.py` | 9 | `config.py` + `api/v1.py` (timeout bound) | 1 |
| `test_api_utility_tasks.py` | 7 | `api/v1.py` (utility routing) | 1 |
| `test_api_streaming.py` | 12 | `api/v1.py` (SSE behaviour) | 1 |
| `test_api_mounting.py` | 5 | `main.py` (real app wiring) | 1.5 — real `app`, mocked graph |
| `test_graph_stateless.py` | 3 | `graph.py` | 1.5 — real graph, fake LLM |
| `test_message_loop_history.py` | 4 | `routes.py` (message loop) | 1 |
| `test_rate_limiter.py` | 16 | `rate_limiter.py` | 1 |
| `test_tools_liturgical_mapping.py` | 10 | `tools.py` (`_map_liturgical_data`) | 1 |
| `test_tools_date_normalization.py` | 23 | `tools.py` (`_normalize_date`) | 1 |
| `test_standard_client.py` | 5 | `a2a_protocol` client | 1 |

Two files are deliberately half-real: `test_graph_stateless.py` builds the **actual**
compiled graph and replaces only `get_llm`, and `test_api_mounting.py` uses the
**actual** `app` object with only `get_graph` patched. Both exist because a fully
mocked test cannot observe wiring.

**Proves:** individual functions and their error paths.
**Cannot prove:** that the pieces are wired together, or that anything runs.

### Level 2 — Container

The built image against the real runtime.

```bash
docker compose up -d --build
docker compose config > /dev/null                 # parses?
docker ps --format '{{.Names}}\t{{.Ports}}'       # host port audit
docker exec openwebui sh -c 'echo $OPENAI_API_BASE_URL'   # env inside the container
```

Checks performed:

- **Host port audit.** Every published port compared against every other. This is what
  caught `openwebui` and `frontend` both claiming 3000 — `docker compose config`
  parses happily with the conflict, so only the audit or an actual `up` finds it.
- **Environment integrity inside the container.** `OPENAI_API_CONFIGS` contains
  `{"X-OpenWebUI-Chat-Id":"{{CHAT_ID}}"}`; the braces must survive Compose's variable
  substitution. Verified with `docker exec`, not by reading the YAML.
- **Key agreement.** The bearer token OpenWebUI sends compared with the one the
  orchestrator validates.
- **Authenticated container-to-container probe.** `GET /v1/models` issued from inside
  the OpenWebUI container. A host-side health check does not prove this path.
- **Runtime failure behaviour.** A streaming request against an unreachable provider,
  which is what exposed the silent `[DONE]`.

**Proves:** the image runs, the wiring is real, the environment arrived intact.
**Cannot prove:** that the application logic produces correct output.

#### LibreChat container checks (2026-09-18)

```bash
docker compose -f docker-compose.yml -f deploy/librechat/docker-compose.librechat.yml \
  config > /dev/null                                            # parses, no warnings
docker logs librechat | tail -20                                # no zod config error
docker exec librechat node -e "fetch('http://chat-orchestrator:8000/v1/models',{headers:{Authorization:'Bearer '+process.env.ORCHESTRATOR_API_KEY}}).then(r=>r.text()).then(console.log)"
```

Observed:

- LibreChat boots and applies the `interface` config to role permissions (prompts,
  memories, bookmarks, multi-convo, agents, temporary chat, web search, file search,
  file citations, marketplace all set to `false`). An invalid `librechat.yaml` would
  have aborted startup instead.
- The container-to-container probe returns the `prete-a-porter` model card — proving
  the bearer key, the internal hostname, and the base URL together.
- `RAG API is either not running or not reachable` is logged as a warning; it is
  expected, since the LibreChat RAG stack is deliberately not deployed.
- The concurrent-download stall: two image pulls of the same tag deadlock each other.
  Pull once, then `up`.

### Level 3 — Integration with a stubbed model

When no model is reachable, a local OpenAI-compatible stub still exercises the whole
chain. The stub answers `/v1/chat/completions` and, on the first turn, requests a
liturgical tool call.

```bash
# terminal 1 — the stub
cd packages/chat-orchestrator && uv run python scripts/stub_llm.py

# terminal 2 — point the orchestrator at it
cat > /tmp/compose.stub.yml <<'EOF'
services:
  chat-orchestrator:
    environment:
      - OPENAI_BASE_URL=http://host.docker.internal:9099/v1
      - OPENAI_API_KEY=stub
      - OPENAI_MODEL_NAME=stub
EOF
docker compose -f docker-compose.yml -f /tmp/compose.stub.yml \
  up -d --force-recreate --no-deps chat-orchestrator
```

A single request then traverses orchestrator → graph → `agent_node` → `tools_node` →
A2A client → `liturgy-agent` → evangelizo.org → back through the graph → OpenAI-shaped
response. Observed result:

```
content: STUB: catena completa. Il tool liturgico ha risposto con 3886 caratteri.
```

The 3886 characters are real scraped liturgical data.

**Restore the real configuration afterwards** with a plain
`docker compose up -d --force-recreate --no-deps chat-orchestrator`; the override file
is not part of the stack.

**Proves:** the agent chain, the A2A transport, authentication, and tool execution.
**Cannot prove:** anything that depends on the model's judgement — whether it *chooses*
the right tool, or whether its tool arguments are well-formed.

### Level 4 — End-to-end with a real model

```bash
KEY=$(awk -F= '/^ORCHESTRATOR_API_KEY=/{print $2}' .env)
curl -s -X POST localhost:8000/v1/chat/completions \
  -H "Authorization: Bearer $KEY" -H "Content-Type: application/json" \
  -H "X-OpenWebUI-User-Id: e2e" -H "X-OpenWebUI-Chat-Id: e2e" \
  -d '{"model":"prete-a-porter","messages":[{"role":"user","content":"preparami l omelia per domenica prossima"}]}'
```

Then, for streaming, the same request with `"stream": true`, and a frame-by-frame
inspection: content-frame count, `[DONE]` termination, and an assertion that no
tool-call payload appears in the stream.

Logs are counted with real timestamps rather than `--since`, which filters on container
time and includes earlier runs:

```bash
docker compose logs homily-agent | grep -E "^homily-agent-1  \| 2026-09-17 08:2[2-9]" \
  | grep -icE "error|validation"
```

**Proves:** the product works.
**Cannot prove:** robustness across models. Three defects (below) appeared only here,
and two of them appeared with one model but not another.

#### LibreChat end-to-end (2026-09-18)

Driven through the real UI in a browser, against the running stack and a real model.
The evidence is the orchestrator's own boundary log, which carries the identity the
LibreChat server forwarded.

| Check | Result |
|---|---|
| `GET /v1/models` from the LibreChat container | `200`, model card |
| Registration, login, first turn through the UI | readings for Sunday 20 September 2026, retrieved via `calculate_date` → `get_liturgical_readings` |
| Streaming turn | `200`, `stream=true`, one request, `outcome=completed` |
| LibreChat → orchestrator identity | `user_id=6aad1f27cde2ae57330e29d7`, `conversation_id=04769b45-…`, `message_id=db022209-…` all present in the log |
| Conversation id stable across turns | three turns, same `conversation_id`, distinct `message_id`s |
| Homily generation through the UI | four sections rendered; 67.7 s |
| Refinement turn | `duration_ms=7224`, `outcome=completed`, same conversation |
| Second user | different `user_id`, different `conversation_id`, empty conversation list — no access to the first user's chat |
| Auxiliary requests | `POST /v1/chat/completions` count equals the turn count: **no title request** |
| Orchestrator restart | conversation reopened by URL with full history intact |
| Timeout with `CHAT_REQUEST_TIMEOUT_SECONDS=5` | `outcome=timeout` at `duration_ms=5017`; LibreChat rendered *"La richiesta ha superato il tempo massimo di elaborazione"* and the stream closed cleanly |
| Recovery after restoring 180 s | next turn `outcome=completed`, same conversation |

**Proves:** a stock, pinned LibreChat is a working client of the boundary, with
per-user isolation, stable thread correlation, and user-visible error handling.
**Cannot prove:** long-run behaviour (token budgets, many concurrent users), and the
LibreChat-side rendering of domain-specific output — that is PR 6+ work.

## What each level caught

| Defect | Found at | Why the lower levels missed it |
|---|---|---|
| `TEST_MODE` mock cannot drive the graph (`bind_tools` returns a coroutine) | 0 | The unit test would have failed with `AttributeError` two frames from the cause |
| `DATABASE_PATH` defaults to `/app`, unwritable outside Docker | 0 | The test failed before reaching its assertion |
| Suite left red between tasks (removed branch still asserted; deleted module still imported) | 1 | Caught during execution, not by review |
| **`openwebui` and `frontend` both publish host port 3000** | 2 | `docker compose config` parses successfully with the conflict |
| **A failed stream emitted only `[DONE]`** — no content, no error | 2 | The unit test asserted "the stream terminates" and passed; nothing asserted what the client *sees* on failure |
| Graph → tools → A2A → scraper chain works | 3 | Requires a running stack |
| **Readings dropped their `type` field** en route to `homily-agent` | 4 | Needs a real model to malform the payload |
| **Model looped until `GraphRecursionError`** | 4 | Needs a model eager enough to keep calling tools |
| **`"next sunday"` reached the liturgy agent verbatim** | 4 | Needs a model that ignores the `calculate_date` instruction |
| `homily-agent` retrieves 0 documents (ChromaDB absent) | 4 | Only visible in a real run's logs |
| **The new boundary log lines never reached the container logs** — stdlib `logging` records find no handler (`configure_logging()` is never called), so `INFO` is dropped and `WARNING` survives only via `logging.lastResort` | 4 | Unit tests read logs through `caplog`, which attaches its own handler — so the test suite could see messages the deployment drops |
| **`CHAT_REQUEST_TIMEOUT_SECONDS` works as designed under a real stream** | 4 | The unit test proves the response shape; only LibreChat proves a user sees the message |

The pattern is worth stating plainly: **levels 0–3 verified everything this migration
built, and level 4 immediately found three defects in code it had not touched.** A
passing unit suite says nothing about whether the system works.

## Known gaps

- **Frontend Playwright suite not run.** `frontend/e2e/*.spec.ts` exists and covers
  registration, chat persistence, and the WebSocket flow. It was not executed because
  the frontend is slated for removal.
- **`contracts/tests/` live and E2E tests not run.** They drive the WebSocket path and
  were left untouched; they need the same revision the WebSocket removal will require.
- **`packages/liturgy-agent` and `packages/homily-agent` have no tests for the changes
  they did not receive.** They were not modified, but their behaviour is only covered
  through the orchestrator's tests and level 4.
- **No coverage measurement.** `pytest-cov` is a dependency but no threshold is
  enforced. The "70% / 80% / 90%" targets in `testing.rst` are not verified by anything.
- **Level 4 depends on one provider account.** A suspended billing account silently
  turns every level-4 check into a 500. Level 3 exists so the chain can still be
  verified without one.
- **Stdlib logging is still half-wired — tracked as a backlog activity in
  `AgentWorklog` (`prete-a-porter/Activities/2026-09-18-stdlib-logging-backlog`).**
  The `/v1` boundary and `identity.py` now use the structured logger
  (`utils.logging.get_logger`), which is what actually emits. `tools.py` (12 call
  sites) and `api/auth.py` still call `logging.getLogger(...)`, and
  `configure_logging()` — the root-handler installer — is never called: their `INFO`
  records are dropped, and their `WARNING` records surface only as bare lines through
  `logging.lastResort`. Verified against the container: `grep -c "Requesting liturgical
  data"` on the logs returns 0 although the tools ran.
