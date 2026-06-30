# Spec: Migrate RAG Vector Store from ChromaDB to Qdrant

**Date:** 2026-07-01
**Status:** Approved — ready for implementation
**Branch:** `feat/qdrant-migration` (to be created)

---

## 1. Problem Statement

The homily-agent's RAG pipeline is **effectively non-functional in Docker images**:

1. **No data in image** — `data/chroma_db/` is gitignored (67 MB locally), Dockerfile doesn't copy it
2. **No volume mount** — `docker-compose.yml` homily-agent has no `volumes:` (unlike chat-orchestrator and liturgy-agent)
3. **Runtime ingestion is a no-op** — `main.py:57` calls `load_theological_corpus()` which looks for `data/theological_corpus/*.txt` (nonexistent)
4. **Manual CLI can't run in-container** — `ingest_corpus.py` needs `support/` data (not in image) + `ml` extra deps (not installed)
5. **EmbeddingService is dead code** — `embeddings.py` is defined and exported but never instantiated; ChromaDB uses its own `ONNXMiniLM_L6_V2` instead
6. **`_chunk_text` infinite-loop bug** (issue #12) — if `overlap >= chunk_size`, `start` never advances
7. **Synchronous retrieval blocks the event loop** — ChromaDB has no async support; `retrieve()` is called in an async path (same class of bug as fixed issue #4)

## 2. Decision: Qdrant Server Mode + AsyncQdrantClient

| Aspect | Choice | Rationale |
|--------|--------|-----------|
| **Deployment** | Server mode (separate `qdrant/qdrant` container) | Fits microservices architecture; built-in dashboard UI at `:6333/dashboard`; dedicated volume; decoupled from homily-agent lifecycle |
| **Client** | `AsyncQdrantClient` | Avoids blocking the event loop in the async homily-agent; Qdrant has first-class async support |
| **Embeddings** | `qdrant-client[fastembed]` extras | Automatic ONNX embeddings via `models.Document`; same model (`sentence-transformers/all-MiniLM-L6-v2`, 384 dims); no torch/sentence-transformers needed |
| **Data migration** | Re-ingest from source | No migration script; run `support/download.sh` + updated `ingest_corpus.py`. The 67 MB local ChromaDB is gitignored and disposable |

## 3. Architecture (Target)

```
┌──────────────────────────────────────────────────────────────┐
│                     USER INTERFACE                            │
│                   (Next.js Web Chat)                          │
└─────────────────────────┬────────────────────────────────────┘
                          │ WebSocket
                          ↓
┌──────────────────────────────────────────────────────────────┐
│                  CHAT ORCHESTRATOR AGENT                      │
│        FastAPI + LangGraph + WebSocket                        │
└──────────┬──────────────────────────────────┬────────────────┘
           │ A2A Protocol                     │ A2A Protocol
           ↓                                  ↓
┌──────────────────────────┐  ┌──────────────────────────────┐
│    LITURGY AGENT         │  │  HOMILY GENERATION AGENT      │
│  LangGraph + LLM         │  │  LangGraph + RAG + Qdrant     │
│  SQLite cache            │  │  fastembed (ONNX)             │
└──────────────────────────┘  └──────────────┬───────────────┘
                                             │ gRPC/REST
                                             ↓
                              ┌──────────────────────────────┐
                              │  QDRANT VECTOR DB             │
                              │  Collection: "corpus"          │
                              │  384-dim cosine, HNSW index    │
                              │  Dashboard: :6333/dashboard    │
                              └──────────────────────────────┘
```

### Docker Compose Topology (New)

```
docker-compose up
  ├── chat-orchestrator  (8000)  → depends_on: liturgy-agent, homily-agent
  ├── liturgy-agent      (8001)  → SQLite cache (./data volume)
  ├── homily-agent       (8002)  → depends_on: qdrant (NEW)
  ├── qdrant             (6333)  → NEW: vector DB, dedicated volume
  ├── frontend           (3000)  → depends_on: chat-orchestrator
  ├── caddy              (80/443)
  └── a2a-inspector      (8080)
```

## 4. Async Cascade

Making `RetrievalService.retrieve()` async cascades through 5 files:

```
retrieval.py:  retrieve() → async, add_documents() → async, reset_collection() → async, delete_collection() → async
    ↓
generator.py:  _retrieve_theological_content() → async, generate() → async
    ↓
agent.py:      generate_homily() → async, refine_homily() → async, adjust_tone() → async
    ↓
graph.py:      _generate_node() → async, _refine_node() → async, _adjust_node() → async
    ↓
main.py:       _ensure_initialized() → async (await load_theological_corpus)
```

Nodes that stay **synchronous** (no I/O, no retrieval):
- `_parse_node` (agent.parse_request — pure data extraction)
- `_validate_node` (agent.validate_homily — checks generated_homily is not None)
- `_format_node` (agent.format_response — formats homily text)

LangGraph handles mixed sync/async nodes when invoked via `ainvoke()` (which `main.py:124` already uses).

## 5. Implementation Steps (Ordered)

### Phase 1: Dependencies

| # | File | Change |
|---|---|---|
| 1 | `packages/homily-agent/pyproject.toml` | Replace `chromadb>=0.5.0,<0.6.0` → `qdrant-client[fastembed]>=1.12.0`. Remove `sentence-transformers` + `torch` from `ml` extra (keep `beautifulsoup4`, `lxml`, `pymupdf` for parsers). Remove `numpy>=1.24.0,<2` if no longer needed (check) |
| 2 | `packages/homily-agent/uv.lock` | Regenerate via `uv lock` |

### Phase 2: Core RAG Rewrite

| # | File | Change |
|---|---|---|
| 3 | `packages/homily-agent/src/homily_agent/rag/retrieval.py` | Complete rewrite — see §6 for detailed API mapping |
| 4 | `packages/homily-agent/src/homily_agent/rag/embeddings.py` | **Delete** — dead code (`EmbeddingService` never called) |
| 5 | `packages/homily-agent/src/homily_agent/rag/__init__.py` | Remove `EmbeddingService` import/export |

### Phase 3: Async Cascade

| # | File | Change |
|---|---|---|
| 6 | `packages/homily-agent/src/homily_agent/generator.py` | Make `_retrieve_theological_content()` and `generate()` async. Add `await` on retrieval call |
| 7 | `packages/homily-agent/src/homily_agent/agent.py` | Make `generate_homily()`, `refine_homily()`, `adjust_tone()` async |
| 8 | `packages/homily-agent/src/homily_agent/graph.py` | Make `_generate_node`, `_refine_node`, `_adjust_node` async. Use `functools.partial` for node wrappers (cleaner than lambda for async) |
| 9 | `packages/homily-agent/src/homily_agent/main.py` | Make `_ensure_initialized()` async. `await load_theological_corpus()` in `__call__` before method dispatch |

### Phase 4: Ingestion Script

| # | File | Change |
|---|---|---|
| 10 | `packages/homily-agent/scripts/ingest_corpus.py` | Wrap `main()` in `asyncio.run(async_main())`. Use async `RetrievalService` methods (`await retrieval.add_documents(...)`, `await retrieval.get_document_count()`, `await retrieval.reset_collection()`) |

### Phase 5: Docker & Config

| # | File | Change |
|---|---|---|
| 11 | `docker-compose.yml` | Add `qdrant` service. Update `homily-agent`: add `QDRANT_URL=http://qdrant:6333` env, `depends_on: qdrant: condition: service_healthy` |
| 12 | `.env.example` | Add `QDRANT_URL`, `QDRANT_COLLECTION`, `RAG_TOP_K`, `RAG_MIN_SIMILARITY` |
| 13 | `packages/homily-agent/Dockerfile` | No changes needed — `uv sync --frozen` installs core deps automatically |

### Phase 6: Documentation

| # | File | Change |
|---|---|---|
| 14 | `AGENTS.md` | Update: ADR-005 (ChromaDB→Qdrant), ADR-006 (sentence-transformers→fastembed), ADR-007 (lazy init still valid), tech stack table, architecture diagram, module table, known issues (remove ChromaDB refs, add Qdrant), config section (QDRANT_URL etc.) |
| 15 | `README.md` | Update RAG section: ChromaDB → Qdrant, mention dashboard |
| 16 | `packages/homily-agent/README.md` | Update RAG setup instructions: `qdrant-client[fastembed]` instead of chromadb, Qdrant container instead of local ChromaDB |

### Phase 7: Tests

| # | File | Change |
|---|---|---|
| 17 | `packages/homily-agent/tests/rag/test_retrieval.py` | **New** — test `RetrievalService` with `AsyncQdrantClient(":memory:")` (no server needed for tests). Test: add_documents, retrieve, get_document_count, reset_collection, empty collection retrieval, min_similarity filtering |
| 18 | `packages/homily-agent/tests/test_graph.py` | Update if async cascade affects test fixtures — likely needs `pytest.mark.asyncio` on tests calling generate/refine nodes |

### Phase 8: CI

| # | File | Change |
|---|---|---|
| 19 | `.github/workflows/unit-tests.yml` | No changes — `qdrant-client[fastembed]` is core dep, installed by `uv sync --extra dev` |
| 20 | `.github/workflows/contract-tests.yml` | No changes — Qdrant is in docker-compose, contract tests use `--no-docker` |

## 6. Detailed API Mapping: ChromaDB → Qdrant

### `RetrievalService.__init__`

```python
# BEFORE (ChromaDB)
persist_directory: str = "data/chroma_db"
collection_name: str = "corpus"

# AFTER (Qdrant)
qdrant_url: str | None = None  # from env QDRANT_URL, e.g. "http://qdrant:6333"
collection_name: str = os.getenv("QDRANT_COLLECTION", "corpus")
# Local fallback: if no QDRANT_URL, use QdrantClient(path="data/qdrant_db")
```

### `_ensure_initialized`

```python
# BEFORE
chromadb.PersistentClient(path=self.persist_directory, settings=Settings(anonymized_telemetry=False))
ef = ONNXMiniLM_L6_V2(preferred_providers=["CPUExecutionProvider"])
self.collection = self.client.get_collection(name, embedding_function=ef)
  # or create_collection(name, metadata={"hnsw:space": "cosine"}, embedding_function=ef)

# AFTER
self.client = AsyncQdrantClient(url=self.qdrant_url)  # or path for local
# Collection creation with explicit vector config:
try:
    await self.client.get_collection(self.collection_name)
except Exception:
    await self.client.create_collection(
        collection_name=self.collection_name,
        vectors_config=models.VectorParams(size=384, distance=models.Distance.COSINE),
    )
```

### `add_documents`

```python
# BEFORE
self.collection.add(documents=documents, ids=ids, metadatas=metadatas)

# AFTER (fastembed auto-embedding)
points = [
    models.PointStruct(
        id=str(uuid.uuid5(uuid.NAMESPACE_DNS, id_str)),  # deterministic UUID from string ID
        vector=models.Document(text=doc, model=EMBEDDING_MODEL),
        payload={**(metadata or {}), "text": doc, "id": id_str},
    )
    for doc, id_str, metadata in zip(documents, ids, metadatas or [{}] * len(documents))
]
await self.client.upsert(collection_name=self.collection_name, points=points, wait=True)
```

### `retrieve`

```python
# BEFORE
results = self.collection.query(query_texts=[query], n_results=self.top_k)
# score = 1.0 - distance (ChromaDB returns distances, lower = closer)

# AFTER (fastembed auto-embedding, Qdrant returns scores, higher = closer)
results = await self.client.query_points(
    collection_name=self.collection_name,
    query=models.Document(text=query, model=EMBEDDING_MODEL),
    limit=self.top_k,
    with_payload=True,
)
# results.points[i].score is cosine similarity (0-1, higher = better)
# Filter: score >= self.min_similarity
```

### `get_document_count`

```python
# BEFORE
return self.collection.count()

# AFTER
info = await self.client.get_collection(self.collection_name)
return info.points_count
```

### `reset_collection`

```python
# BEFORE
self.client.delete_collection(name)
self.client.create_collection(name, metadata={"hnsw:space": "cosine"}, embedding_function=ef)

# AFTER
await self.client.delete_collection(self.collection_name)
await self.client.create_collection(
    collection_name=self.collection_name,
    vectors_config=models.VectorParams(size=384, distance=models.Distance.COSINE),
)
```

### `delete_collection`

```python
# BEFORE
self.client.delete_collection(name)

# AFTER
await self.client.delete_collection(self.collection_name)
```

### `load_theological_corpus`

```python
# BEFORE: sync function, calls retrieval_service.add_documents() directly

# AFTER: async function, awaits retrieval_service.add_documents()
# Also fix _chunk_text infinite-loop bug (#12):
#   Add guard: if overlap >= chunk_size: raise ValueError(...)
#   Or: clamp overlap = min(overlap, chunk_size - 1)
```

### ID Conversion

Qdrant requires integer or UUID IDs. Current string IDs (`"doc_genesis_chunk_0"`) need conversion:

```python
import uuid
EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"

def _to_uuid(id_str: str) -> str:
    """Convert string ID to deterministic UUID (for Qdrant upsert semantics)."""
    return str(uuid.uuid5(uuid.NAMESPACE_DNS, id_str))
```

UUID5 is deterministic — same string always produces the same UUID, preserving upsert semantics (re-ingesting the same document updates rather than duplicates).

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `QDRANT_URL` | `http://qdrant:6333` | Qdrant server URL (docker network). If unset, falls back to local mode `path="data/qdrant_db"` |
| `QDRANT_COLLECTION` | `corpus` | Collection name (same as before) |
| `RAG_TOP_K` | `5` | Number of documents to retrieve (unchanged) |
| `RAG_MIN_SIMILARITY` | `0.7` | Minimum cosine similarity threshold (unchanged) |
| `EMBEDDING_MODEL` | `sentence-transformers/all-MiniLM-L6-v2` | fastembed model name (replaces unused sentence-transformers env var) |

## 7. Docker Compose — Qdrant Service

```yaml
  # Qdrant Vector Database - theological knowledge base for RAG
  # Dashboard available at http://localhost:6333/dashboard
  qdrant:
    image: qdrant/qdrant:latest
    ports:
      - "6333:6333"   # REST API + dashboard
      - "6334:6334"   # gRPC API
    volumes:
      - qdrant_data:/qdrant/storage
    networks:
      - preteaporter-network
    healthcheck:
      test: ["CMD", "bash", "-c", "exec 3<>/dev/tcp/localhost/6333 && echo -e 'GET /healthz HTTP/1.0\\r\\nhost: localhost\\r\\n\\r\\n' >&3 && grep '200' <&3"]
      interval: 10s
      timeout: 5s
      start_period: 5s
      retries: 5
    restart: unless-stopped
```

Homily-agent changes:
```yaml
  homily-agent:
    # ... existing config ...
    environment:
      - AGENT_CONTRACT_PATH=/app/contracts/homily-agent-contract.json
      - AGENT_URL=http://homily-agent:8002
      - A2A_BASIC_AUTH_USERNAME=${A2A_BASIC_AUTH_USERNAME}
      - A2A_BASIC_AUTH_PASSWORD=${A2A_BASIC_AUTH_PASSWORD}
      - QDRANT_URL=http://qdrant:6333                    # NEW
      - QDRANT_COLLECTION=${QDRANT_COLLECTION:-corpus}    # NEW
      - RAG_TOP_K=${RAG_TOP_K:-5}                        # NEW
      - RAG_MIN_SIMILARITY=${RAG_MIN_SIMILARITY:-0.7}    # NEW
    depends_on:
      qdrant:
        condition: service_healthy                        # NEW
```

New volume:
```yaml
volumes:
  frontend-db:
  caddy_data:
  caddy_config:
  qdrant_data:   # NEW
```

## 8. What Stays Out of Scope

| Item | Reason |
|------|--------|
| Generator template placeholder (`generator.py:290`) | Separate feature — wiring LLM into generation. This migration only swaps the vector DB backend |
| Bible abbreviation inconsistency (issue #9) | Unrelated to Qdrant migration |
| `_format_node` discarding return value (issue #11) | Unrelated bug, same pattern as fixed #5 |
| GHCR workflow changes | Qdrant uses official Docker Hub image, not built by us |
| Dockerfile changes | `uv sync --frozen` installs new core dep automatically |

## 9. ADR Updates

### ADR-005 (updated 2026-07-01)

| | |
|---|---|
| **Decision** | Qdrant as vector store (replacing ChromaDB) |
| **Rationale** | Server mode fits microservices architecture; built-in dashboard for inspection; first-class async client; fastembed provides ONNX embeddings without torch; dedicated container with healthcheck |
| **Trade-offs** | Extra container in docker-compose (minor); Qdrant image ~50 MB; no local embedded mode in production (local mode available for dev/tests via `:memory:`) |

### ADR-006 (updated 2026-07-01)

| | |
|---|---|
| **Decision** | fastembed (ONNX) for embeddings (replacing sentence-transformers) |
| **Rationale** | Bundled with `qdrant-client[fastembed]`; same model (`all-MiniLM-L6-v2`, 384 dims); no torch dependency; automatic embedding via `models.Document` |
| **Trade-offs** | Limited to fastembed-supported models; no access to custom sentence-transformer models |

### ADR-007 (updated 2026-07-01)

| | |
|---|---|
| **Decision** | Lazy init RAG in homily agent (unchanged) |
| **Rationale** | Qdrant client + fastembed are lighter than ChromaDB + ONNX, but lazy init still avoids unnecessary connection on health checks and import-time failures |
| **Trade-offs** | First request is slower (Qdrant connection + collection check); error surfaces at runtime not at import |

## 10. Verification Plan

| Step | Command | Expected |
|------|---------|----------|
| Unit tests | `cd packages/homily-agent && uv run pytest -v` | All pass, including new `test_retrieval.py` |
| Lock file | `cd packages/homily-agent && uv lock --check` | Lock file in sync with pyproject.toml |
| Docker build | `docker compose build homily-agent` | Image builds without error |
| Qdrant startup | `docker compose up qdrant` | Healthcheck passes, dashboard at `:6333/dashboard` |
| Homily agent startup | `docker compose up homily-agent` | `/health` returns 200 |
| Empty retrieval | `curl -X POST localhost:8002/ -d '{"jsonrpc":"2.0","id":"1","method":"homily.generate","params":{...}}'` | Returns homily with `sources: []` (empty Qdrant, no crash) |
| Ingestion | `uv run python scripts/ingest_corpus.py --reset` | Populates Qdrant collection, `get_document_count` > 0 |
| RAG retrieval | Same homily.generate call after ingestion | Returns homily with `sources: [...]` (non-empty) |
| Contract tests | `cd contracts && uv run pytest tests/ -v --no-docker` | 42 passed, 3 skipped (unchanged) |
