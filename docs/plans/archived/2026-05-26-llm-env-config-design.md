# LLM Env Var Configuration Design

## Overview

Rendere configurabili tramite environment variables l'API endpoint (base URL) e il nome del modello per ogni provider LLM. Raggruppare i provider per standard API invece che per vendor, eliminando provider ridondanti.

## Motivation

Il factory `create_llm()` in `packages/a2a-protocol/src/a2a_protocol/llm.py` permetteva di scegliere il provider LLM solo tramite API key (per priority order). Modello e base URL erano hardcodati per ogni factory. Questo impediva:
- Uso di provider OpenAI-compatibili (Fireworks, Groq, Together, Ollama, vLLM) senza aggiungere nuove factory
- Test con endpoint locali/proxy personalizzati
- Override del modello senza modificare codice

## Decisioni

### 1. Raggruppamento per standard API (non per vendor)

Abbiamo 3 famiglie di API, non 4:

| Famiglia | Provider inclusi | Factory |
|----------|-----------------|---------|
| **Anthropic** | Claude | `ChatAnthropic` |
| **Google Gemini** | Gemini | `ChatGoogleGenerativeAI` |
| **OpenAI-compatibile** | OpenAI, Fireworks, Groq, Together, Ollama, vLLM | `ChatOpenAI` |

**Alternativa scartata:** Tenere `_create_fireworks()` come factory separata. Motivo: Fireworks è un'API OpenAI-compatibile, non serve codice dedicato. Basta cambiare `OPENAI_BASE_URL`.

### 2. Fireworks rimosso come provider first-class

Rimossa `FIREWORKS_API_KEY` e `_create_fireworks()`. Fireworks si usa settando `OPENAI_API_KEY` + `OPENAI_BASE_URL`.

Rimossa anche la dipendenza opzionale `langchain-fireworks` da `pyproject.toml`.

### 3. Modello leggibile da env var per ogni factory

Ogni factory function legge il modello da una env var specifica, con fallback allo stesso default hardcodato di prima:

- `ANTHROPIC_MODEL_NAME` → default `claude-3-5-sonnet-20241022`
- `GOOGLE_MODEL_NAME` → default `gemini-flash-lite-latest`
- `OPENAI_MODEL_NAME` → default `gpt-4-turbo-preview`

### 4. Base URL non passato esplicitamente

`ChatAnthropic` già supporta `ANTHROPIC_BASE_URL` / `ANTHROPIC_API_URL` nativamente via costruttore. `ChatOpenAI` già supporta `OPENAI_BASE_URL`. Google non supporta base URL custom. Non serve codice nuovo.

### 5. `preferred_model` e `prefer_google` rimossi

Entrambi inutilizzati dai consumer. `preferred_model` era buggato (forzava un nome modello cross-provider). `prefer_google` è sostituibile dall'ordine delle chiavi (non settare `ANTHROPIC_API_KEY` se vuoi Google).

### 6. Provider selection per priority order

Il primo provider con API key settata vince:
1. `ANTHROPIC_API_KEY`
2. `GOOGLE_API_KEY`
3. `OPENAI_API_KEY`

## File modificati

| File | Cambiamento |
|------|------------|
| `packages/a2a-protocol/src/a2a_protocol/llm.py` | Factory riscritta: 3 provider, env var per modello, niente base URL esplicito |
| `packages/a2a-protocol/pyproject.toml` | Rimosso `fireworks = ["langchain-fireworks"]` |
| `.env.example` | Nuove env var con esempi per provider OpenAI-compatibili |
| `AGENTS.md` | Sezione 8 espansa con provider selection ed env var table |
| `packages/chat-orchestrator/src/chat_orchestrator/config.py` | Docstring: `ChatFireworks` → `ChatOpenAI` |
| `docs/plans/archived/refactoring-plan.md` | Riferimenti al vecchio factory aggiornati |

## Storia delle decisioni

| Data | Decisione |
|------|-----------|
| 2026-05-26 | Raggruppamento per standard API (Anthropic, Google, OpenAI) |
| 2026-05-26 | Fireworks rimosso come provider separato, ora sotto OpenAI-compatibile |
| 2026-05-26 | Modello leggibile da env var per provider |
| 2026-05-26 | `preferred_model` e `prefer_google` rimossi |
