# Env Var Implementations Plan

**Goal:** Implement 4 env vars documented in AGENTS.md but never wired to code: `CACHE_TTL_SECONDS`, `RAG_TOP_K`, `RAG_MIN_SIMILARITY`, `EMBEDDING_MODEL`

**Pattern:** All follow the same approach — env var read as fallback default in the constructor, explicit parameter still takes precedence (for testing).

---

## Task 1: `CACHE_TTL_SECONDS` in `LiturgyCache`

**File:** `packages/liturgy-agent/src/liturgy_agent/cache.py`

**What changes:**
- Constructor reads `CACHE_TTL_SECONDS` from env var, converts seconds→hours, stores as `self.default_ttl_hours`
- `set()` method uses `self.default_ttl_hours` when `ttl_hours` not explicitly passed
- `DEFAULT_TTL_HOURS = 24` stays as hardcoded fallback

**Specific edits:**

1. Add `import os` at top (already has `from datetime import datetime, timedelta` + others)
2. In `__init__`, after `self.db_path = db_path`:
   ```python
   ttl_seconds = os.getenv("CACHE_TTL_SECONDS")
   self.default_ttl_hours = int(ttl_seconds) // 3600 if ttl_seconds else self.DEFAULT_TTL_HOURS
   ```
3. In `set()` method, change signature to make `ttl_hours` optional and use `self.default_ttl_hours`:
   ```python
   def set(self, reading: LiturgicalReading, ttl_hours: int | None = None) -> None:
       ttl = ttl_hours if ttl_hours is not None else self.default_ttl_hours
       expires_at = datetime.utcnow() + timedelta(hours=ttl)
   ```

**Consumer:** `LiturgyCache()` called with no args in `agent.py:58` — picks up env var automatically.

---

## Task 2: `RAG_TOP_K` and `RAG_MIN_SIMILARITY` in `RetrievalService`

**File:** `packages/homily-agent/src/homily_agent/rag/retrieval.py`

**What changes:**
- Constructor parameters `top_k` and `min_similarity` become `int | None = None` and `float | None = None`
- If `None`, read from env var with hardcoded fallback

**Specific edits:**

1. In `__init__` signature and body:
   ```python
   def __init__(
       self,
       persist_directory: str = "data/chroma_db",
       collection_name: str = "corpus",
       top_k: int | None = None,
       min_similarity: float | None = None
   ):
       self.persist_directory = persist_directory
       self.collection_name = collection_name
       self.top_k = top_k if top_k is not None else int(os.getenv("RAG_TOP_K", "5"))
       self.min_similarity = min_similarity if min_similarity is not None else float(os.getenv("RAG_MIN_SIMILARITY", "0.7"))
   ```

**Consumer:** `RetrievalService()` called with no args in `main.py:60` and `retrieval.py:220` — picks up env vars.

**Note:** `os` is already imported at the top.

---

## Task 3: `EMBEDDING_MODEL` in `EmbeddingService`

**File:** `packages/homily-agent/src/homily_agent/rag/embeddings.py`

**What changes:**
- Constructor parameter `model_name` becomes `str | None = None`
- If `None`, read from `EMBEDDING_MODEL` env var with hardcoded fallback

**Specific edits:**

1. In `__init__` signature and body:
   ```python
   def __init__(
       self,
       model_name: str | None = None,
       device: str | None = None
   ):
       self.model_name = model_name or os.getenv("EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
       self.device = device or ("cuda" if os.environ.get("CUDA_VISIBLE_DEVICES") else "cpu")
       self.model: Any | None = None
   ```

**Consumer:** `EmbeddingService` is not directly instantiated in the codebase (no `EmbeddingService(` calls found via grep), but this makes it configurable when used.

---

## Verification

After all tasks, run:
```bash
pytest packages/liturgy-agent/tests/ --no-header -q
pytest packages/homily-agent/tests/ --no-header -q
```

Expected: same results as before (all existing tests pass, no regressions).
