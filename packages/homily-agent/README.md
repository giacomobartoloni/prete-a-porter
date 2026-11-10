# homily-agent

Homily generation agent. Communicates via the standard **Google A2A protocol**.

## Generation and refinement

The homily service owns Italian prose generation. It uses the shared provider
factory and composes four sections from full supplied readings, user preferences
and bounded retrieved passages. Refinement sends the complete existing draft and
new instructions to the model for a substantive rewrite.

`preferences.target_word_count` (50–3000) overrides the legacy length choice.
Without it, short/medium/long target 650/1100/1600 words. Section content must
fall within ±15% of the target; headings do not count. `preferences.instructions`
(up to 4000 characters) carries the full request, celebration and example.
Invalid JSON, blank sections or wrong length receive one corrective attempt.
For a valid draft with the wrong length, the second call is a focused editor:
it receives that draft and user constraints, without duplicating the original
long draft or retrieval context. Short drafts additionally retain the readings
for factual expansion.
After the second attempt, structurally valid prose that is still too long may
be shortened by removing the minimum necessary complete sentences from the
introduction and reading reflection. This edit is limited to drafts no more than 40% above the upper word limit.
The practical example, conclusion, first
sentences, quoted passages and ambiguous abbreviation boundaries are protected.
No words are invented and no sentence is cut midstream. If this conservative
edit cannot reach the range, the request fails. Short or malformed output is
never repaired this way. Sentence removal is an editorial fallback and does not
guarantee semantic coherence; inspect real output when qualifying a model.
Persistent invalid output or provider failure returns an error; no template is
substituted. A valid structure/count is not a theological or factual evaluation.

Retrieved context is limited to 12000 serialized JSON characters (including source labels), at most 2500 per
passage. Only model-selected source IDs that correspond to supplied passages are
reported. This records declared context use, not independently verified citation
entailment. When no usable corpus is available, the model uses the supplied
scripture and reports no theological sources.

Runtime limits are explicit and provider-specific tuning is supported:

| Variable | Default | Meaning |
|---|---|---|
| `HOMILY_MODEL_TIMEOUT_SECONDS` | `45` | Per composition attempt; SDK retries disabled |
| `HOMILY_MAX_OUTPUT_TOKENS` | `4096` | Provider output cap; set within your model's supported ceiling |
| `HOMILY_OPENAI_REASONING_EFFORT` | unset | Optional reasoning control for a supporting OpenAI-compatible model; never sent to other providers |
| `HOMILY_OPENAI_JSON_MODE` | `false` | Opt-in `response_format=json_object` for a supporting OpenAI-compatible provider |
| `HOMILY_REQUEST_TIMEOUT_SECONDS` | `110` | Orchestrator's A2A homily deadline; set greater than two model attempts plus retrieval overhead |

The homily transport makes one HTTP attempt, so a timed-out expensive generation
is not duplicated automatically. Keep the outer `CHAT_REQUEST_TIMEOUT_SECONDS`
large enough for the homily call plus orchestration (default 180 seconds).
A synchronous provider call runs in the LangGraph worker rather than the event
loop. Cancellation stops the caller promptly but cannot forcibly interrupt an
already running worker; remaining work is bounded by the configured provider
timeout and at most one corrective call. A long requested text may exceed a
model's output limit: increase the cap only for a supporting model, or request a
shorter text; truncated/invalid prose is rejected. No setting guarantees a latency
or model-quality target without measuring the selected provider.

Provider packages for OpenAI-compatible, Anthropic and Google models are installed
through the existing A2A extras. `TEST_MODE=true` uses deterministic fixture prose
and disables real retrieval/model calls. It tests plumbing, not content quality.

## Corpus lifecycle and provenance

Ingestion upserts stable document IDs, so rerunning unchanged input does not add
duplicates and existing IDs receive corrected text. The generic `.txt` loader
uses relative paths rather than basenames, preserving distinct nested sources.
Collections created by the old generic loader require an explicit operator-run
reset/reindex to remove legacy IDs; no automatic migration deletes existing data.
Likewise, upserting a shorter source does not remove obsolete trailing chunks:
use a full reset/reindex when the source set or chunk layout changes.

`--reset` now clears an existing collection even in a fresh CLI process.
Retrieval excludes results without finite distance evidence. Chroma still uses
the local ONNX MiniLM embedding function; `EMBEDDING_MODEL` on the separate
sentence-transformers helper does not change this runtime path. Model changes
require a compatible embedding profile, a separate reindex and quality evaluation.

## Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/` | Standard A2A JSON-RPC (`message/send`) |
| `GET` | `/.well-known/agent-card.json` | Agent Card |
| `GET` | `/tasks/{id}` | Get task status |
| `GET` | `/tasks` | List tasks |
| `GET` | `/health` | Health check |

## Skills

Callable via `message/send` with text `{"method":"...","params":{}}`:

| Method | Description |
|---|---|
| `agent.ping` | Health check, returns pong |
| `homily.generate` | Generate a homily from liturgical data |
| `homily.refine` | Refine an existing homily |
| `homily.adjust_tone` | Adjust tone of a homily |

## Quick Start

```bash
# Start the agent
uv run python -m homily_agent.main --port 8002

# Ping
curl -s http://localhost:8002/health

# Generate a homily
curl -s -X POST http://localhost:8002/ \
  -H 'Content-Type: application/json' \
  -d '{
    "jsonrpc": "2.0",
    "id": "1",
    "method": "message/send",
    "params": {
      "message": {
        "role": "user",
        "parts": [{"text": "{\"method\":\"homily.generate\",\"params\":{\"occasion\":\"mass\"}}"}]
      }
    }
  }'
```

## Docker

```bash
docker compose up homily-agent
```

Build rapido (~1s) — le dipendenze pesanti per RAG/embeddings sono opzionali.

## Dependencies

Per l'uso base (senza RAG) basta installare il core:

```bash
uv sync
```

Per abilitare RAG/embeddings chromaDB + torch, usa l'extra `ml`:

```bash
uv sync --extras ml
```

> **Nota:** `torch`, `sentence-transformers` e `chromadb` sono in `[project.optional-dependencies] ml` per mantenere il build rapido. L'agente funziona senza, con graceful fallback.

## Structure

- `src/homily_agent/main.py` — Entry point + A2A handler
- `src/homily_agent/agent.py` — LangGraph agent
- `src/homily_agent/generator.py` — Homily generation logic
- `src/homily_agent/rag/` — RAG retrieval + theological corpus (opzionale)

## Corpus Ingestion

Popola ChromaDB con Bibbia CEI 2008 e Catechismo della Chiesa Cattolica per il RAG:

```bash
# Prerequisiti: dipendenze ML
uv sync --extras ml

# Ingest completo (default: support/bibbia2008/bcei2008/ + support/catechismo/...pdf)
uv run python scripts/ingest_corpus.py

# Reset e re-ingest
uv run python scripts/ingest_corpus.py --reset

# Path personalizzati
uv run python scripts/ingest_corpus.py --bible-dir /percorso/bibbia --ccc-path /percorso/ccc.pdf
```

Il corpus viene salvato in `data/chroma_db/` (persist directory di ChromaDB).

Da Docker (senza installare torch/bs4 sull'host), tramite il servizio one-off
`rag-ingest` di `docker-compose.yml`:

```bash
docker compose build homily-agent
docker compose run --rm rag-ingest --reset     # aggiungi --help per le opzioni
```

I parser (bs4/lxml/pymupdf) vengono installati nel container al volo; gli
embedding usano la stessa funzione ONNX MiniLM del retrieval a runtime.
`support/` è montato read-only, `data/chroma_db/` è condiviso con `homily-agent`.


Reasoning controls are an explicit provider/model profile choice, not the
default for every deployment; unsupported models may reject the option.
Confirm provider support before enabling it and qualify the complete workflow,
rather than selecting a mode solely from a single fast response.
See [Fireworks reasoning controls](https://docs.fireworks.ai/api-reference/post-chatcompletions).


The local Fireworks profile also enables JSON object mode, documented in
[Fireworks structured responses](https://docs.fireworks.ai/structured-responses/structured-response-formatting).
This constrains syntax; section/count validation still runs, and an output-token
limit can still truncate JSON. Other compatible providers must explicitly opt
in after support is checked. No such parameter is sent to Anthropic or Google.


For the tested DeepSeek V4.1 Flash profile, reasoning `none` was fast but failed
length adherence repeatedly. The final local qualification uses `low`, cap8192,
and JSON object mode: two complete browser workflows measured499→220 and503→209
body words after reload. This profile takes longer and one isolated generation
still exhausted8192 tokens. Treat these as scenario measurements; select supported
budgets and verify complete workflows for another deployment or model.
