# Phase 2 & 3 Plan — Open Points Resolution

## 8 task, dalla più impattante alla più semplice

---

## Task A: Eliminare il copy-paste nell'Homily Agent (punto 5/13)

### Analisi

3 metodi in `packages/homily-agent/src/homily_agent/main.py` condividono >80% di codice:

```
_generate_homily (42 righe)  — intent="generate"
_refine_homily    (38 righe)  — intent="refine"   + existing_draft
_adjust_tone      (36 righe)  — intent="adjust"
```

Differenze: solo `intent` Literal e presenza di `existing_draft`.

### Soluzione

Estrarre un metodo `_invoke_graph()` condiviso:

```python
async def _invoke_graph(
    self,
    params: Dict[str, Any],
    intent: Literal["generate", "refine", "adjust"],
) -> Dict[str, Any]:
    """Execute graph with given parameters and intent."""
    from .state import HomilyAgentState, LiturgicalReading, UserPreferences
    from .graph import GraphState

    liturgical_data = params.get("liturgical_data")
    occasion = params.get("occasion", "mass")
    preferences = params.get("preferences", {})
    existing_draft = params.get("existing_draft")

    lit_reading = LiturgicalReading(**liturgical_data) if liturgical_data else None
    user_prefs = UserPreferences(**preferences) if preferences else UserPreferences()

    initial_state = HomilyAgentState(
        intent=intent,
        liturgical_data=lit_reading,
        occasion=occasion,
        user_preferences=user_prefs,
        existing_draft=existing_draft,
    )

    graph_state: GraphState = {"homily_state": initial_state}
    final_state = self.graph.invoke(graph_state)
    homily_state = final_state["homily_state"]

    return {
        "homily": homily_state.generated_homily.model_dump() if homily_state.generated_homily else None,
        "sources": homily_state.theological_sources or [],
    }
```

E ridurre i 3 metodi a 2 righe ciascuno:

```python
async def _generate_homily(self, params):
    return {"status": "success", "data": await self._invoke_graph(params, "generate")}

async def _refine_homily(self, params):
    return {"status": "success", "data": await self._invoke_graph(params, "refine")}

async def _adjust_tone(self, params):
    return {"status": "success", "data": await self._invoke_graph(params, "adjust")}
```

**Rischio**: Medio. Cambia il comportamento di `_refine_homily` che ora restituisce anche `sources` (prima no). Nessun impatto sul client — riceve più dati.

---

## Task B: Eliminare lo stato mutabile globale in tools.py (punto 19)

### Analisi

`packages/chat-orchestrator/src/chat_orchestrator/tools.py`:

```python
_liturgy_client = None   # riga 88
_homily_client = None    # riga 91
```

Usati in 28 punti: ogni funzione che chiama un agente controlla se `_xxx_client is None`, lo crea, lo usa, ma non c'è mai una `close()` se non in funzioni `close_liturgy_client()` e `close_homily_client()` che **nessuno chiama mai**.

### Soluzione

**Opzione A (semplice)**: Ogni funzione crea e chiude un client in un context manager:

```python
async def request_liturgical_data(occasion: str, date: Optional[str] = None):
    from a2a_protocol import a2a_client
    
    config = _get_liturgy_transport_config()
    
    async with a2a_client(**config) as client:
        result = await client.call(
            method="liturgy_agent.get_readings",
            params={"occasion": occasion, "date": normalized_date or _today_iso()},
            timeout=60.0,
        )
    return result
```

**Pro**: nessuno stato globale, thread-safe, connection pool pulito.
**Contro**: crea+apre+chiude una connessione HTTP ad ogni chiamata (minimo overhead per agenti locali via HTTP).

**Rischio**: Basso. Pattern standard `async with`. Overhead trascurabile.

---

## Task C: Aggiungere exception chaining `from e` (punto 9)

### Analisi

24 raise in liturgy agent senza `from e`:

| File | Raise | Righe |
|---|---|---|
| `liturgy-agent/main.py` | `raise ValueError(...)` | 82, 102, 110, 192, 210, 227 |
| `liturgy-agent/scrapers.py` | `raise ScraperError(...)` | 60, 124, 128, 135, 181, 253, 310, 315, 371, 375, 492 |

Ogni raise è dentro un `except` block (o dopo un check che ha fallito). Vanno aggiunti:

```python
# PRIMA (es. main.py:110):
except ValueError:
    raise ValueError(f"Invalid date format: {date_str}. Use YYYY-MM-DD")

# DOPO:
except ValueError as e:
    raise ValueError(f"Invalid date format: {date_str}. Use YYYY-MM-DD") from e
```

**Per ogni raise va verificato** se è dentro un `except` block o meno:

- **main.py:82** — `raise ValueError(f"Unknown method: {method}")` — NON dentro except, nessun `from e` necessario
- **main.py:102** — `if not occasion: raise ValueError(...)` — non dentro except, OK
- **main.py:110** — dentro `except ValueError` → `from e`
- **main.py:192** — dentro `except FileNotFoundError` → `from e`
- **main.py:210** — `if not occasion: raise ValueError(...)` — non dentro except, OK  
- **main.py:227** — dentro `except FileNotFoundError` → `from e`
- **scrapers.py:60** — dentro `except ImportError` → `from e`
- **scrapers.py:124** — dentro `except httpx.HTTPError` → `from e`
- **scrapers.py:128** — non dentro except, OK
- **scrapers.py:135** — non dentro except, OK
- **scrapers.py:181** — dentro `if not data: raise` — non dentro except, OK
- **scrapers.py:253** — non dentro except, OK
- **scrapers.py:310** — dentro `except ImportError` → `from e`
- **scrapers.py:315** — dentro `except ImportError` → `from e`
- **scrapers.py:371** — dentro `except httpx.HTTPError` → `from e`
- **scrapers.py:375** — non dentro except, OK
- **scrapers.py:492** — `if not results: raise` — non dentro except, OK

**Rischio**: Basso. È solo aggiungere `from e` a 9 raise esistenti.

---

## Task D: Aggiungere config ruff/mypy a tutti i pyproject.toml (punto 14)

### Soluzione

Aggiungere a tutti e 4 i `pyproject.toml`:

```toml
[tool.ruff]
line-length = 120
target-version = "py312"

[tool.ruff.lint]
select = ["E", "W", "F", "I", "B", "C4", "UP", "SIM"]
ignore = ["E501"]

[tool.mypy]
python_version = "3.12"
strict = true
warn_return_any = true
```

**Rischio**: Nessuno. Config solo, non esecuzione.

---

## Task E: Fix naming `Evangelize_Scraper` (punto 16)

### Analisi

`packages/liturgy-agent/src/liturgy_agent/scrapers.py:40`:

```python
class Evangelize_Scraper:  # Underscore tra parole → viola PascalCase
```

Tutti gli altri nomi nella file sono corretti: `VaticanScraper`, `ScraperError`.

### Riferimenti

```python
rtk grep -n "Evangelize_Scraper" packages/liturgy-agent/
```

Va rinominato e aggiornati tutti i riferimenti.

**Rischio**: Basso. Solo rename.

---

## Task F: Fix `sunday_or_weekday` type drift (punto 21)

### Analisi

| File | Tipo |
|---|---|
| `liturgy-agent/state.py:43` | `Literal["Sunday", "Weekday"]` |
| `homily-agent/state.py:43` | `str` |

### Soluzione

```python
# homily-agent/state.py:43
sunday_or_weekday: Literal["Sunday", "Weekday"]  # invece di str
```

**Rischio**: Basso. Aggiunge vincolo, non lo toglie.

---

## Task G: `_parse_intent` keyword matching (punto 20)

### Analisi

`packages/liturgy-agent/src/liturgy_agent/agent.py:498-526`:

```python
async def _parse_intent(query: str, llm: Any) -> list[str]:
    query_lower = query.lower()
    if "marriage" in query_lower or "wedding" in query_lower:
        return ["occasion"]
    elif "baptism" in query_lower:
        return ["occasion"]
    ...
    else:
        return ["daily"]
```

Usa keyword matching semplice. Il parametro `llm: Any` è passato ma mai usato.

### Soluzione

Due opzioni:

**Opzione A (semplice)**: Rimuovere il parametro `llm` inutilizzato. Mantenere keyword matching.

**Opzione B (completa)**: Usare LLM per intent parsing. Ma è overkill dato che il keyword matching funziona per i casi d'uso attuali (occasion → marriage/baptism/funeral, daily → mass/sunday/weekday, search → search/find).

**Consiglio**: Opzione A. Rimuovere `llm` inutilizzato, documentare il mapping.

**Rischio**: Basso.

---

## Task H: Verificare Volume Mount DB (punto 24)

### Analisi

Dal `docker-compose.yml`:

```yaml
volumes:
  - ./data/chat_orchestrator.db:/app/data/chat_orchestrator.db
  - ./data/liturgy_cache.db:/app/data/liturgy_cache.db
```

Il default di `create_graph()` ora è `/app/data/chat_orchestrator.db` — corrisponde al mount. Ma:

1. `chat-orchestrator` non ha `DATABASE_PATH` esplicitamente settato in `environment:` in docker-compose
2. Il liturgy agent cache scrive in `sqlite:///...` con un path che potrebbe non corrispondere

### Verifica necessaria

Leggere `packages/liturgy-agent/src/liturgy_agent/cache.py` per vedere il path effettivo usato dalla cache.

**Rischio**: Basso. Il default ora corrisponde.

---

## Summary

| Task | File | Righe modificate | Rischio | Complessità |
|---|---|---|---|---|
| **A** Homily copy-paste | `homily-agent/main.py` | ~120→~50 | 🟡 Medio | Media |
| **B** Global state | `chat-orchestrator/tools.py` | ~20 | 🟢 Basso | Bassa |
| **C** Exception chaining | `liturgy-agent/main.py`, `scrapers.py` | 9 righe | 🟢 Basso | Bassa |
| **D** ruff/mypy config | 4 × `pyproject.toml` | 4×10 righe | 🟢 Basso | Bassa |
| **E** `Evangelize_Scraper` | `liturgy-agent/scrapers.py` | 1 riga + refs | 🟢 Basso | Bassa |
| **F** `sunday_or_weekday` | `homily-agent/state.py` | 1 riga | 🟢 Basso | Bassa |
| **G** `_parse_intent` cleanup | `liturgy-agent/agent.py` | 1 riga | 🟢 Basso | Bassa |
| **H** DB path verify | `docker-compose.yml` + `cache.py` | 1-2 righe | 🟢 Basso | Bassa |

### Ordine di esecuzione

```
D (config) → E (naming) → F (type) → G (cleanup)
↓
A (homily) → C (chaining)
↓
B (global state) → H (verify)
```

D, E, F, G sono indipendenti e banali. A e C sono nel homily/liturgy agent. B ha impatto su tools.py e va testato. H verifica finale.
