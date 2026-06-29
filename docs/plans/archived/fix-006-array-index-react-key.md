# Fix #6 — Array index as React key in Chat.tsx

**Severity**: Critical
**File**: `frontend/src/components/Chat.tsx:209`
**Report**: `docs/code-review-report.html` (#6)

## Problema

```tsx
messages.map((message, index) => (
  <div key={index} ...
```

Usare `key={index}` impedisce a React di tracciare correttamente i messaggi quando ne arrivano di nuovi via WebSocket, causando re-render incorretti e potenziale perdita di stato DOM.

## Soluzione

Aggiungere `id: string` a ogni messaggio con `crypto.randomUUID()` e usarlo come key.

## Perché `crypto.randomUUID()`

- Native nel browser (UUIDv4, 122 bit di entropia)
- Native in Node.js 22.19 (globale, safe per SSR)
- Nessuna dipendenza aggiuntiva
- Nessun rischio hydration mismatch: `messages` parte da `[]`, i messaggi nascono solo da interazione utente

## Step

| # | File | Cosa |
|---|------|------|
| 1 | `frontend/src/types/index.ts:3` | Aggiungere `id: string` (required) a `BaseMessage` |
| 2 | `frontend/src/components/Chat.tsx:89-95` | `id: crypto.randomUUID()` in LiturgicalMessage |
| 3 | `frontend/src/components/Chat.tsx:98-105` | `id:` in HomilyMessage |
| 4 | `frontend/src/components/Chat.tsx:108-114` | `id:` in PreferenceMessage |
| 5 | `frontend/src/components/Chat.tsx:122-128` | `id:` in TextMessage (content blocks) |
| 6 | `frontend/src/components/Chat.tsx:135-140` | `id:` in TextMessage (fallback) |
| 7 | `frontend/src/components/Chat.tsx:146-151` | `id:` in user message (sendMessage) |
| 8 | `frontend/src/components/Chat.tsx:209` | `key={index}` → `key={message.id}` |
| 9 | `docs/code-review-report.html` | Marcare #6 come Resolved |
| 10 | Frontend Docker | `docker compose build frontend` |
| 11 | E2E | `npx playwright test` |

## Altri `key={index}` nel frontend

Trovati anche in `HomilyDisplay.tsx:75` e `PreferencePicker.tsx:52,71,90` — ma su liste statiche che non mutano dopo il render (Finding #29, minor). Fuori scope.
