# Fix #8: Blocking `graph.invoke()` inside async handler

**Finding:** `packages/homily-agent/src/homily_agent/main.py:124`

**Problema:** `self.graph.invoke(graph_state)` è sincrono ma chiamato dentro `async def _invoke_graph()`. Durante la generazione dell'omelia (potenzialmente secondi), l'event loop asyncio è bloccato.

**Fix (1 riga):**
```python
# Prima (bloccante):
final_state = self.graph.invoke(graph_state)

# Dopo (non bloccante):
final_state = await self.graph.ainvoke(graph_state)
```

**Dipendenze:** LangGraph ≥0.3.0 (progetto usa `langgraph>=0.3.0`) — `CompiledGraph.ainvoke()` disponibile da 0.1.x. Esegue nodi sync in threadpool.

**Non in scope:**
- `graph.py:186` — `run_homily_generation()` è una funzione sync, `.invoke()` è corretto
- Le funzioni nodo (`_parse_node`, `_generate_node`, etc.) rimangono sync — `ainvoke` le gestisce in threadpool

**Test:** `pytest packages/homily-agent/tests/` (solo parser RAG, nessun test diretto del grafo)
**Lint:** `ruff check packages/homily-agent/`

**Impatto:** Minimo — 1 carattere cambiato (`invoke` → `ainvoke` + `await`)
