# homily-agent

Homily generation agent. Communicates via the standard **Google A2A protocol**.

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
