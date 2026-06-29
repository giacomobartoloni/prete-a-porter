# Prete-a-porter — Pre-Publishing Audit

> Generato il 2026-05-26 · Aggiornato al commit `b9a3c6d`

## Stato

| Priorità | Risolti | Aperti |
|----------|---------|--------|
| 🔴 BLOCKER | 3/3 | 0 |
| 🟠 HIGH | 4/6 | 2 |
| 🟡 MEDIUM | 2/6 | 4 |
| ⚪ LOW/NICE | 0/8 | 8 |

---

## 🔴 BLOCKER — must fix before publishing

### ~~B1 — Hardcoded absolute filesystem path in `contracts/pyproject.toml`~~ ✅

- **File**: `contracts/pyproject.toml:14`
- ~~`"a2a-protocol @ file:///Users/gbartoloni/projects/learning/preteaporter/packages/a2a-protocol"`~~
- **Fix**: Sostituire con `"a2a-protocol"` + `[tool.uv.sources]` con path relativo.
- **Risolto**: commit `36812b4`

### ~~B2 — Build artifacts `contracts.egg-info/` tracciati in git~~ ✅

- ~~`contracts/contracts.egg-info/PKG-INFO`, `SOURCES.txt`, ...~~
- **Fix**: `git rm -r --cached contracts/contracts.egg-info/`
- **Risolto**: commit `36812b4` (`.gitignore` già aveva `*.egg-info`)

### ~~B3 — `validation_output.txt` tracciato in git~~ ✅

- ~~`validation_output.txt` (root)~~
- **Fix**: Aggiungere a `.gitignore` + `git rm --cached`
- **Risolto**: commit `36812b4`

---

## 🟠 HIGH — should fix before publishing

### ~~H1 — Contenuto coperto da copyright: `support/bibbia2008/` (~12 MB, 126 file)~~ ✅

- ~~75+ file HTML della Bibbia CEI 2008 + 41 immagini JPG + GIF + ICO + PNG + CSS~~
- ~~`support/catechismo/catechismo-della-chiesa-cattolica.pdf`~~
- **Fix**: `git rm -r support/`, `.gitignore` blocca le sottodirectory, script `support/download.sh` per fetch da fonte originale.
- **Risolto**: commit `3ab54b6` (resta nella history git, non purgato)

### ~~H2 — `.python-version` vs `pyproject.toml`: mismatch~~ ✅

- ~~`.python-version:1` → `3.13` vs `pyproject.toml` → `>=3.12` / CI → `3.12`~~
- **Fix**: Allineare `.python-version` a `3.12`.
- **Risolto**: commit `b9a3c6d`

### ~~H3 — Licenza~~ ✅

- **Fix**: Aggiunto `LICENSE` (GNU AGPLv3), aggiornati README e package metadata.
- **Risolto**: commit 

### ~~H4 — Piani di fix risolti in branch principale~~ ✅

- ~~`docs/plans/fix-006-array-index-react-key.md`, `fix-008-blocking-graph-invoke.md`, `fix-009-validate-node-discards-results.md`, `fix-024-dark-mode-class-toggle.md`~~
- **Fix**: Archiviare in `docs/plans/archived/`.
- **Risolto**: commit `b9a3c6d`

### ~~H5 — Refactoring plan duplicato~~ ✅

- ~~`docs/plans/refactoring-plan.md` e `docs/plans/archived/refactoring-plan.md` (1.179 righe, identici)~~
- **Fix**: Rimosso `docs/plans/refactoring-plan.md` (tenuta copia in archived).
- **Risolto**: commit `b9a3c6d`

### H6 — Email placeholder poco professionale

- **Files**: Tutti e 5 i `pyproject.toml` (e relativi `.egg-info/PKG-INFO`)
- **Problema**: `contributors@preteaporter.local` — dominio `.local` non risolvibile.
- **Fix**: Usare `team@example.com` o un indirizzo vero, o rimuovere il campo `authors`.

---

## 🟡 MEDIUM — recommended before publishing

| # | Cosa | File | Fix | Stato |
|---|------|------|-----|-------|
| M1 | Riferimenti a `backend/` nei doc Sphinx | `docs/index.rst:13`, `docs/testing.rst:503`, `docs/introduction.rst:36,163` | Aggiornare a `packages/` o rimuovere | ❌ |
| M2 | `DARK-DESIGN.md` in posizione ambigua | `docs/DARK-DESIGN.md` (ex root) | Verificare sia gitignored | ❌ |
| ~~M3~~ | ~~`.gitignore` lacunoso~~ | ~~`.gitignore`~~ | ~~Aggiungere `*.egg-info`, `support/`, `docs/code-review-report.html`~~ | ✅ |
| M4 | Specifica archiviata con riferimenti obsoleti | `docs/archived/SPECIFICATION_PLAN.md` (1.919 righe, 40+ ref a `backend/`) | Accettabile in archived, ma confusionario | ❌ |
| ~~M5~~ | ~~Report HTML generato in git~~ | ~~`docs/code-review-report.html` (1.132 righe)~~ | ~~Aggiungere a `.gitignore`~~ | ✅ |
| ~~M6~~ | ~~`.env.example` del frontend incompleto~~ | ~~`frontend/.env.example` (solo 1 var)~~ | ~~Sincronizzare con root `.env.example`~~ | ✅ |

---

## ⚪ LOW / NICE

| # | Cosa | Note | Stato |
|---|------|------|-------|
| L1 | PDF Catechismo nella storia git | Anche rimosso da HEAD, resta nella history (`a10e048 documentazione`) | ❌ |
| L2 | `SPECIFICATION.md` in due posti archived | `docs/archived/` e `docs/plans/archived/` — deduplicare | ❌ |
| L3 | Nessun lockfile Python a root | Solo `contracts/uv.lock` esiste. Nessuna riproducibilità globale. | ❌ |
| L4 | healthcheck retries inconsistenti | `chat-orchestrator:3` vs `liturgy/homily:10` in `docker-compose.yml` | ❌ |
| L5 | Root `package.json` prisma 5 vs frontend 6 | `package.json:8` → `^5.22.0`, frontend → `^6.5.0` | ❌ |
| L6 | Stub `docs/backend/` .rst inesistenti | `docs/backend/index.rst` ecc. non buildano più | ❌ |
| N1 | CI hardcoded Python 3.12 | Usare `python-version-file: .python-version` | ❌ |
| N2 | CI setta `LITURGY_LLM_PROVIDER: mock` ma nessun codice lo legge | Variabili morte | ❌ |

---

## Cosa funziona già ✓

- Nessun segreto/API key esposto in git
- `.gitignore` robusto (`.env`, `node_modules/`, `__pycache__/`, `.venv/`, `data/`, `*.egg-info`, `support/`, `docs/code-review-report.html`, `validation_output.txt` coperti)
- Git history pulita (nessun merge sporco, commit convenzionali)
- `README.md` completo
- CI workflow presente e funzionale
- Nessun TODO/FIXME/HACK nei sorgenti Python/TS
- Path assoluto rimosso da `contracts/pyproject.toml`
- `.python-version` allineato a `3.12`
- Fix plan spostati in archived, refactoring plan deduplicato
- `frontend/.env.example` sincronizzato con root
