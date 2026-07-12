# Chat Persistence Design

**Date:** 2026-05-22
**Status:** Approved for implementation

## Problem

Users cannot save, resume, or delete chat conversations. Messages exist only in React memory — page refresh loses the conversation. The `sessionId` is randomly generated on mount, making it impossible to reconnect to an existing LangGraph checkpoint.

## Design Decisions

- **Data location:** Frontend (Next.js + Prisma) — the frontend already has User/Session auth models
- **Message storage:** `messages` as JSON array embedded in the Conversation record (same pattern as Open WebUI)
- **History delivery:** Always sent via WebSocket with each message, not via LangGraph checkpointer
- **History invalidation:** If the checkpointer loses state (crash/restart), the frontend re-sends history automatically

## Prisma Schema

```prisma
model Conversation {
  id        String   @id @default(uuid())
  userId    String
  sessionId String   @unique           // = LangGraph thread_id for WS
  title     String   @default("Nuova conversazione")
  messages  String   @default("[]")    // JSON array: [{role, content, contentType, timestamp}]
  createdAt DateTime @default(now())
  updatedAt DateTime @updatedAt

  user User @relation(fields: [userId], references: [id], onDelete: Cascade)
}
```

## API Routes (Next.js)

| Method | Path | Purpose |
|--------|------|---------|
| `POST` | `/api/conversations` | Create new conversation, generate `sessionId` |
| `GET` | `/api/conversations` | List user's conversations `{id, title, updatedAt}` |
| `GET` | `/api/conversations/[id]` | Get conversation with full `messages` array |
| `PATCH` | `/api/conversations/[id]` | Update title or messages array |
| `DELETE` | `/api/conversations/[id]` | Delete conversation |

All routes are authenticated via NextAuth session.

## WebSocket Protocol

### Send (client → orchestrator)

```json
{
  "text": "Contenuto del messaggio",
  "history": [
    {"role": "user", "content": "Messaggio precedente", "contentType": "text"},
    {"role": "assistant", "content": "...", "contentType": "liturgical"}
  ]
}
```

### Receive (orchestrator → client)

Unchanged from current format. Same type-discriminated responses.

## Data Flow

### Create new conversation
```
User clicks "Nuova chat"
  → POST /api/conversations → { id, sessionId }
  → Frontend stores sessionId
  → WebSocket connect with sessionId
  → LangGraph creates new thread
```

### Send message (normal flow)
```
User sends message
  → Frontend saves user message to Prisma (PATCH)
  → WebSocket sends { text, history } (history from Prisma messages)
  → Orchestrator processes via LangGraph
  → Response received via WS
  → Frontend saves AI response to Prisma (PATCH)
```

### Resume conversation (page refresh / later return)
```
User opens existing conversation
  → GET /api/conversations/[id] → returns { messages: [...] }
  → Frontend renders all messages
  → WebSocket connect with stored sessionId
  → LangGraph loads existing checkpoint (or starts fresh if lost)
  → First user message sends full history from Prisma
  → After that, LangGraph checkpointer has the context
```

### Delete conversation
```
User clicks "Elimina"
  → DELETE /api/conversations/[id]
  → Removes from Prisma
  → Optionally: DELETE /conversations/:sessionId on orchestrator to clean checkpoint
```

## Chat Orchestrator Changes

**Minimal.** Only the WebSocket message loop (`routes.py:_message_loop`):

- Accept JSON `{ text, history }` instead of raw text
- Merge history into LangGraph messages array
- Add `DELETE /conversations/:sessionId` endpoint (optional, for checkpoint cleanup)

No changes to tools, A2A protocol, LangGraph graph, or other agents.

## Frontend Changes

### Components
- **`Chat.tsx`**: Modified to send `{ text, history }` via WS; save responses to Prisma; load history from Prisma on mount
- **`Sidebar.tsx`**: Extended to list conversations and allow switching/deleting
- **New component**: Conversation list in sidebar (or extracted to its own component)

### State management
- `messages[]` initialized from Prisma on conversation load
- On each WS response, update `messages[]` state + persist to Prisma (PATCH)
- `sessionId` stored in component state (from Conversation record)

## UI / UX

- Sidebar shows list of conversations: `{title, updatedAt relative}`
- Click conversation → loads and connects
- "Nuova conversazione" button at top
- Delete button (trash icon) on hover or via menu
- Auto-title from first user message (first 50 chars, or default "Nuova conversazione")

## Error Handling

- **Orchestrator crash mid-conversation**: WS disconnects. On reconnect, frontend re-sends history → conversation resumes
- **Prisma save fails**: Messages stay in React state. Show non-blocking error toast. Retry on next message
- **Conversation load fails**: Show error state with retry option

## Non-goals (explicitly excluded)

- Search within conversations
- Pinning / archiving
- Folder organization
- Multi-model branching
- Conversation export
