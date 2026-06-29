# Occasion Mismatch: "wedding" vs "marriage" Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Align `contracts/homily-agent-contract.json` with the codebase by renaming `"wedding"` to `"marriage"` in the occasion enum.

**Architecture:** Single value change in the homily agent contract JSON, plus documentation updates. No runtime code changes needed — the contract is loaded only for self-description (Agent Card), never for request validation. All Python, TypeScript, and test files already use `"marriage"`.

**Tech Stack:** JSON, Markdown (docs), HTML (report)

---

### Task 1: Fix the contract JSON

**Files:**
- Modify: `contracts/homily-agent-contract.json:97`

- [ ] **Step 1: Change "wedding" to "marriage" in the contract enum**

```json
// Line 97: change from this:
"enum": ["mass", "wedding", "funeral", "baptism"]

// to this:
"enum": ["mass", "marriage", "funeral", "baptism"]
```

- [ ] **Step 2: Verify the JSON is still valid**

Run: `python -c "import json; json.load(open('contracts/homily-agent-contract.json')); print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add contracts/homily-agent-contract.json
git commit -m "#11: Fix occasion enum in homily agent contract — 'wedding' → 'marriage'"
```

---

### Task 2: Update code-review-report.html

**Files:**
- Modify: `docs/code-review-report.html`

- [ ] **Step 1: Mark Finding #11 as Resolved**

Read the report HTML to find the Finding #11 section (around line 554). Change its badge from "Unresolved" (or whatever style) to "Resolved" with the commit hash. Add the commit hash to the hero summary line count.

Typical badge pattern used in the report for other resolved findings:
```html
<span style="... resolved style ...">Resolved</span>
```

- [ ] **Step 2: Verify HTML is well-formed**

Run: `python -c "import html.parser; parser = html.parser.HTMLParser(); parser.feed(open('docs/code-review-report.html').read()); print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add docs/code-review-report.html
git commit -m "Update report: #11 Resolved (occasion mismatch fix)"
```

---

### Task 3: Update AGENTS.md

**Files:**
- Modify: `AGENTS.md`

- [ ] **Step 1: Mark Finding #11 as Resolved in the known issues table**

Line 475 has the row:
```
| 8 | Important | `Occasion` mismatch: contract `"wedding"` vs code `"marriage"` | `contracts/homily-agent-contract.json:97` |
```

Change to:
```
| 8 | Important | `Occasion` mismatch: contract `"wedding"` vs code `"marriage"` | **Resolved (commit `HASH`)** |
```

Also update the summary count in the table header if there's one.

Line 294 has a description of the issue — add `**Resolved**` or a resolved badge next to it.

- [ ] **Step 2: Verify markdown syntax**

Read the file and do a visual check.

- [ ] **Step 3: Commit**

```bash
git add AGENTS.md
git commit -m "Update AGENTS.md: #11 marked Resolved"
```

---

### Task 4: Contract regression check (contract tests only — no deploy needed)

**Files:**
- Run: `contracts/tests/test_homily_agent_e2e.py` (parametrized with `"marriage"`)
- Run: `contracts/tests/test_homily_contract.py` (no occasion enum assertions, just smoke)

- [ ] **Step 1: Verify the existing e2e tests still pass**

Run: `cd packages/homily-agent && uv run pytest ../../contracts/tests/test_homily_agent_e2e.py -v -k "marriage" 2>&1 || echo "Agent not running — skipping"`

Expected: Tests pass OR are skipped (agent not running). No failures.

- [ ] **Step 2: (Optional) Add a contract validation test**

In `contracts/tests/test_homily_contract.py`, add a test that asserts `"marriage"` is in the occasion enum (to guard against regression):

```python
def test_contract_occasion_enum_includes_marriage(self):
    contract = load_contract()
    generate_method = next(m for m in contract["methods"] if m["name"] == "homily.generate")
    occasion_enum = generate_method["params"]["properties"]["occasion"]["enum"]
    assert "marriage" in occasion_enum
    assert "wedding" not in occasion_enum
```

- [ ] **Step 3: Commit**

```bash
git add contracts/tests/test_homily_contract.py
git commit -m "Add regression test: contract occasion enum uses 'marriage' not 'wedding'"
```

---

### Task 5: Rebuild Docker images (optional, for complete verification)

- [ ] **Step 1: Rebuild homily agent Docker image**

```bash
docker compose build homily-agent
```

- [ ] **Step 2: Verify contract path loads correctly in container**

The homily agent references the contract at `main.py:162`: relative path from `packages/homily-agent/src/homily_agent/main.py` → `contracts/homily-agent-contract.json`. Verify the Docker build succeeds with no errors.
