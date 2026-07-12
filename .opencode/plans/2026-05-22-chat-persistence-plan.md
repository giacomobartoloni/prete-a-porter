# Chat Persistence Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Allow users to save, resume, and delete chat conversations, with messages persisted across sessions.

**Architecture:** Messages and metadata stored in Prisma (frontend Next.js API routes). Chat orchestrator LangGraph checkpointer remains for agent internal state. WebSocket carries `{text, history}` for recovery. Checkpoint cleanup via cascade delete + background TTL task.

**Tech Stack:** Prisma + SQLite (frontend), LangGraph AsyncSqliteSaver (orchestrator), FastAPI (orchestrator REST), Next.js API routes.

---

## File Structure

```
frontend/
  prisma/
    schema.prisma                  # + Conversation model
  src/
    app/
      api/
        conversations/
          route.ts                 # GET (list), POST (create)
          [id]/
            route.ts               # GET, PATCH, DELETE
    components/
      Chat.tsx                     # WS {text, history}, save to Prisma
      Sidebar.tsx                  # Conversation list, switch, delete
    lib/
      conversations.ts             # Client functions (fetch, create, ...)
    types/
      index.ts                     # + Conversation type

packages/chat-orchestrator/
  src/chat_orchestrator/
    routes.py                      # WS message loop: accept {text, history}
    main.py                        # + DELETE /checkpoints/{session_id}
    cleanup.py                     # Background task: TTL purge
```

---

### Task 1: Prisma — Add Conversation model

**Files:**
- Modify: `frontend/prisma/schema.prisma`

Add after Session model:

```prisma
model Conversation {
  id        String   @id @default(uuid())
  userId    String
  sessionId String   @unique
  title     String   @default("Nuova conversazione")
  messages  String   @default("[]")
  createdAt DateTime @default(now())
  updatedAt DateTime @updatedAt

  user User @relation(fields: [userId], references: [id], onDelete: Cascade)

  @@index([userId])
}
```

- [ ] **Step 1: Add model to schema**

Edit `frontend/prisma/schema.prisma` to add the Conversation model.

- [ ] **Step 2: Run migration**

```bash
cd frontend && npx prisma migrate dev --name add_conversations
```

Expected: new migration file created, schema applied.

- [ ] **Step 3: Commit**

```bash
git add frontend/prisma/
git commit -m "feat(db): add Conversation model"
```

---

### Task 2: Frontend — Add Conversation type

**Files:**
- Modify: `frontend/src/types/index.ts`

- [ ] **Step 1: Add types**

Add to `frontend/src/types/index.ts`:

```typescript
export interface Conversation {
  id: string;
  userId: string;
  sessionId: string;
  title: string;
  messages: string;
  createdAt: string;
  updatedAt: string;
}

export interface HistoryMessage {
  role: 'user' | 'assistant';
  content: string;
  contentType?: string;
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/types/index.ts
git commit -m "feat(types): add Conversation and HistoryMessage types"
```

---

### Task 3: Frontend — Conversations lib (client)

**Files:**
- Create: `frontend/src/lib/conversations.ts`

- [ ] **Step 1: Write the file**

```typescript
import { Conversation } from '@/types';

const BASE = '/api/conversations';

export async function listConversations(): Promise<Conversation[]> {
  const res = await fetch(BASE);
  if (!res.ok) throw new Error('Failed to list conversations');
  return res.json();
}

export async function createConversation(): Promise<Conversation> {
  const res = await fetch(BASE, { method: 'POST' });
  if (!res.ok) throw new Error('Failed to create conversation');
  return res.json();
}

export async function getConversation(id: string): Promise<Conversation> {
  const res = await fetch(`${BASE}/${id}`);
  if (!res.ok) throw new Error('Failed to get conversation');
  return res.json();
}

export async function updateConversation(
  id: string,
  data: Partial<Pick<Conversation, 'title' | 'messages'>>
): Promise<Conversation> {
  const res = await fetch(`${BASE}/${id}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
  if (!res.ok) throw new Error('Failed to update conversation');
  return res.json();
}

export async function deleteConversation(id: string): Promise<void> {
  const res = await fetch(`${BASE}/${id}`, { method: 'DELETE' });
  if (!res.ok) throw new Error('Failed to delete conversation');
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/lib/conversations.ts
git commit -m "feat(api): add conversation API client functions"
```

---

### Task 4: Frontend — API routes (POST, GET list)

**Files:**
- Create: `frontend/src/app/api/conversations/route.ts`

- [ ] **Step 1: Write the route**

```typescript
import { NextResponse } from 'next/server';
import { auth } from '@/lib/auth';
import prisma from '@/lib/prisma';
import crypto from 'crypto';

export async function GET() {
  const session = await auth();
  if (!session?.user?.id) {
    return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
  }

  const conversations = await prisma.conversation.findMany({
    where: { userId: session.user.id },
    orderBy: { updatedAt: 'desc' },
    select: { id: true, title: true, updatedAt: true, createdAt: true },
  });

  return NextResponse.json(conversations);
}

export async function POST() {
  const session = await auth();
  if (!session?.user?.id) {
    return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
  }

  const conversation = await prisma.conversation.create({
    data: {
      userId: session.user.id,
      sessionId: crypto.randomUUID(),
    },
  });

  return NextResponse.json(conversation);
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/app/api/conversations/route.ts
git commit -m "feat(api): add POST and GET /api/conversations"
```

---

### Task 5: Frontend — API routes (GET, PATCH, DELETE by id)

**Files:**
- Create: `frontend/src/app/api/conversations/[id]/route.ts`

- [ ] **Step 1: Write the route**

```typescript
import { NextResponse } from 'next/server';
import { auth } from '@/lib/auth';
import prisma from '@/lib/prisma';

export async function GET(
  _req: Request,
  { params }: { params: { id: string } }
) {
  const session = await auth();
  if (!session?.user?.id) {
    return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
  }

  const conv = await prisma.conversation.findFirst({
    where: { id: params.id, userId: session.user.id },
  });
  if (!conv) {
    return NextResponse.json({ error: 'Not found' }, { status: 404 });
  }

  return NextResponse.json(conv);
}

export async function PATCH(
  req: Request,
  { params }: { params: { id: string } }
) {
  const session = await auth();
  if (!session?.user?.id) {
    return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
  }

  const body = await req.json();
  const conv = await prisma.conversation.findFirst({
    where: { id: params.id, userId: session.user.id },
  });
  if (!conv) {
    return NextResponse.json({ error: 'Not found' }, { status: 404 });
  }

  const updated = await prisma.conversation.update({
    where: { id: params.id },
    data: {
      ...(body.title !== undefined && { title: body.title }),
      ...(body.messages !== undefined && { messages: JSON.stringify(body.messages) }),
    },
  });

  return NextResponse.json(updated);
}

export async function DELETE(
  _req: Request,
  { params }: { params: { id: string } }
) {
  const session = await auth();
  if (!session?.user?.id) {
    return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
  }

  const conv = await prisma.conversation.findFirst({
    where: { id: params.id, userId: session.user.id },
  });
  if (!conv) {
    return NextResponse.json({ error: 'Not found' }, { status: 404 });
  }

  await prisma.conversation.delete({ where: { id: params.id } });

  // Notify orchestrator to delete checkpoint (fire & forget)
  const orchestratorUrl = process.env.ORCHESTRATOR_URL || 'http://localhost:8000';
  fetch(`${orchestratorUrl}/checkpoints/${conv.sessionId}`, { method: 'DELETE' }).catch(() => {});

  return NextResponse.json({ success: true });
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/app/api/conversations/[id]/route.ts
git commit -m "feat(api): add GET, PATCH, DELETE /api/conversations/[id]"
```

---

### Task 6: Frontend — Update Chat.tsx with persistence

**Files:**
- Modify: `frontend/src/components/Chat.tsx`

- [ ] **Step 1: Rewrite Chat.tsx**

Key changes:
- Accept `conversationId` prop (or derive from URL params)
- On mount: if `conversationId`, load messages from Prisma via `getConversation(id)`
- On send: send `JSON.stringify({ text, history: messages.map(...) })` instead of raw text
- On receive: save user+assistant exchange to Prisma via `updateConversation(id, { messages: [...] })`
- Auto-generate title from first user message (first 50 chars)
- `sessionId` comes from Conversation record, not `Math.random()`

The WebSocket host is derived from existing config endpoint.

(Rewrite details too long for this plan — implement based on the design spec.)

- [ ] **Step 2: Commit**

```bash
git add frontend/src/components/Chat.tsx
git commit -m "feat(chat): send {text, history} via WS and persist to Prisma"
```

---

### Task 7: Frontend — Update Sidebar with conversation list

**Files:**
- Modify: `frontend/src/components/Sidebar.tsx`

- [ ] **Step 1: Add conversation management to Sidebar**

Changes:
- On mount, call `listConversations()` to populate sidebar list
- Each item: title + relative date
- Active conversation highlighted
- Delete button (trash icon) on hover → calls `deleteConversation(id)`
- "Nuova conversazione" button → calls `createConversation()` → redirects to new chat
- Click item → loads that conversation

- [ ] **Step 2: Commit**

```bash
git add frontend/src/components/Sidebar.tsx
git commit -m "feat(sidebar): add conversation list, create, delete"
```

---

### Task 8: Chat orchestrator — Accept `{text, history}` in WebSocket

**Files:**
- Modify: `packages/chat-orchestrator/src/chat_orchestrator/routes.py`

- [ ] **Step 1: Update `_message_loop` to handle JSON payload**

Change the receive path and graph invocation:

```python
import json

async def _message_loop(websocket: WebSocket, graph, session_id: str, correlation_id: str) -> None:
    message_count = 0

    while True:
        try:
            data = await websocket.receive_text()
        except WebSocketDisconnect:
            raise

        message_count += 1

        try:
            payload = json.loads(data)
            text = payload.get("text", data)
            history = payload.get("history", [])
        except json.JSONDecodeError:
            text = data
            history = []

        # Check if checkpointer has state for this thread
        try:
            checkpointer = graph.checkpointer
            checkpoint = await checkpointer.get_tuple(
                {"configurable": {"thread_id": session_id}}
            )
            has_checkpoint = checkpoint is not None
        except Exception:
            has_checkpoint = False

        if has_checkpoint:
            # Checkpointer alive — pass only new message
            msgs = [HumanMessage(content=text)]
        else:
            # Checkpointer lost — rebuild from history
            msgs = [HumanMessage(content=h["content"]) for h in history if h.get("content")]
            msgs.append(HumanMessage(content=text))

        try:
            result = await graph.ainvoke(
                {"messages": msgs, "session_id": session_id},
                config={"configurable": {"thread_id": session_id}, "recursion_limit": 15},
            )

            ai_messages = [m for m in result["messages"] if isinstance(m, AIMessage)]
            raw_content = ai_messages[-1].content if ai_messages else "No response"
            if isinstance(raw_content, list):
                ai_message = "\n".join(
                    b.get("text", "") for b in raw_content if isinstance(b, dict) and b.get("type") == "text"
                ) or str(raw_content)
            elif not isinstance(raw_content, str):
                ai_message = str(raw_content)
            else:
                ai_message = raw_content

            await websocket.send_json({
                "type": "message",
                "content": ai_message,
                "session_id": session_id,
            })
        except Exception as e:
            logger.error("Error processing message", error=str(e), exc_info=True)
            await websocket.send_json({
                "type": "error",
                "error": {
                    "code": "MESSAGE_PROCESSING_ERROR",
                    "message": "Si è verificato un errore nel processare il messaggio. Riprova.",
                    "correlation_id": correlation_id,
                },
            })
```

- [ ] **Step 2: Commit**

```bash
git add packages/chat-orchestrator/src/chat_orchestrator/routes.py
git commit -m "feat(orchestrator): accept {text, history} in WS message loop"
```

---

### Task 9: Chat orchestrator — `DELETE /checkpoints/{session_id}`

**Files:**
- Modify: `packages/chat-orchestrator/src/chat_orchestrator/main.py`

- [ ] **Step 1: Add the endpoint**

Add import and route to the existing FastAPI app in `main.py`:

```python
from fastapi import Response

@router.delete("/checkpoints/{session_id}")
async def delete_checkpoint(session_id: str):
    try:
        from .graph import get_graph
        graph = await get_graph()
        await graph.checkpointer.adelete_thread(session_id)
    except Exception:
        # Thread doesn't exist or other error — still return 204
        pass
    return Response(status_code=204)
```

- [ ] **Step 2: Verify it compiles**

```bash
uv run python -c "from chat_orchestrator.main import app; print('OK')"
```

- [ ] **Step 3: Commit**

```bash
git add packages/chat-orchestrator/src/chat_orchestrator/main.py
git commit -m "feat(orchestrator): add DELETE /checkpoints/:session_id endpoint"
```

---

### Task 10: Chat orchestrator — Background cleanup task

**Files:**
- Create: `packages/chat-orchestrator/src/chat_orchestrator/cleanup.py`
- Modify: `packages/chat-orchestrator/src/chat_orchestrator/main.py`

- [ ] **Step 1: Create cleanup module**

```python
"""Background task for cleaning up old checkpoints."""

import os
import logging
from datetime import datetime, timedelta, timezone

logger = logging.getLogger(__name__)


async def cleanup_old_checkpoints(graph) -> int:
    ttl_days = int(os.getenv("CHECKPOINT_TTL_DAYS", "90"))
    cutoff = datetime.now(timezone.utc) - timedelta(days=ttl_days)
    deleted = 0

    try:
        async for checkpoint in graph.checkpointer.alist():
            ts_str = checkpoint.checkpoint.get("ts")
            if not ts_str:
                continue
            try:
                ts = datetime.fromisoformat(ts_str)
                if ts < cutoff:
                    thread_id = checkpoint.config["configurable"]["thread_id"]
                    await graph.checkpointer.adelete_thread(thread_id)
                    deleted += 1
            except (ValueError, TypeError):
                continue
    except Exception as e:
        logger.error("Cleanup iteration failed", error=str(e))

    logger.info("Cleanup complete: deleted %d old checkpoints", deleted)
    return deleted
```

- [ ] **Step 2: Wire lifespan into main.py**

Replace or modify the FastAPI app creation to use lifespan:

```python
from contextlib import asynccontextmanager
from .cleanup import cleanup_old_checkpoints
from .graph import get_graph
import asyncio


@asynccontextmanager
async def lifespan(app: FastAPI):
    graph = await get_graph()
    cleanup_task = asyncio.create_task(_periodic_cleanup(graph))
    yield
    cleanup_task.cancel()
    try:
        await cleanup_task
    except asyncio.CancelledError:
        pass


async def _periodic_cleanup(graph):
    """Run cleanup every 24 hours."""
    interval = int(os.getenv("CHECKPOINT_CLEANUP_INTERVAL", "86400"))
    while True:
        await asyncio.sleep(interval)
        try:
            await cleanup_old_checkpoints(graph)
        except Exception as e:
            logger.error("Periodic cleanup failed", error=str(e))


# In create_app() or at module level:
# app = FastAPI(lifespan=lifespan, ...)
```

- [ ] **Step 3: Verify it compiles**

```bash
uv run python -c "from chat_orchestrator.cleanup import cleanup_old_checkpoints; print('OK')"
```

- [ ] **Step 4: Commit**

```bash
git add packages/chat-orchestrator/src/chat_orchestrator/cleanup.py
git add packages/chat-orchestrator/src/chat_orchestrator/main.py
git commit -m "feat(orchestrator): add periodic checkpoint TTL cleanup"
```

---

### Task 11: Tests — Orchestrator checkpoint recovery

**Files:**
- Create or modify: `packages/chat-orchestrator/tests/test_checkpoint_recovery.py`

- [ ] **Step 1: Write tests**

```python
"""Tests for checkpoint recovery and DELETE endpoint."""

import json
import pytest
from unittest.mock import AsyncMock, patch


@pytest.mark.asyncio
async def test_message_loop_rebuilds_from_history_when_no_checkpoint():
    """When checkpointer returns None, _message_loop should use history from WS payload."""
    from chat_orchestrator.routes import _message_loop

    # Mock websocket that sends one JSON message then disconnects
    websocket = AsyncMock()
    websocket.receive_text = AsyncMock(side_effect=[
        json.dumps({
            "text": "Ciao",
            "history": [
                {"role": "user", "content": "Primo messaggio"},
                {"role": "assistant", "content": "Prima risposta"},
            ]
        }),
        WebSocketDisconnect(),
    ])

    # Mock graph with checkpointer that returns None
    mock_checkpointer = AsyncMock()
    mock_checkpointer.get_tuple = AsyncMock(return_value=None)

    graph = AsyncMock()
    graph.checkpointer = mock_checkpointer
    graph.ainvoke = AsyncMock(return_value={
        "messages": [AsyncMock(content="Risposta nuova")]
    })

    with pytest.raises(WebSocketDisconnect):
        await _message_loop(websocket, graph, "test-session", "corr-id")

    # Graph should have been called with history + new message
    call_args = graph.ainvoke.call_args
    msgs = call_args[0][0]["messages"]
    assert len(msgs) == 3  # 2 history + 1 new
    assert msgs[0].content == "Primo messaggio"
    assert msgs[-1].content == "Ciao"


@pytest.mark.asyncio
async def test_message_loop_uses_checkpointer_when_available():
    """When checkpointer has state, history from WS should be ignored."""
    from chat_orchestrator.routes import _message_loop

    websocket = AsyncMock()
    websocket.receive_text = AsyncMock(side_effect=[
        json.dumps({
            "text": "Nuovo messaggio",
            "history": [
                {"role": "user", "content": "Vecchio messaggio"},
            ]
        }),
        WebSocketDisconnect(),
    ])

    mock_checkpointer = AsyncMock()
    mock_checkpointer.get_tuple = AsyncMock(return_value={"checkpoint": {}})

    graph = AsyncMock()
    graph.checkpointer = mock_checkpointer
    graph.ainvoke = AsyncMock(return_value={
        "messages": [AsyncMock(content="Risposta")]
    })

    with pytest.raises(WebSocketDisconnect):
        await _message_loop(websocket, graph, "test-session", "corr-id")

    # Graph should be called with only the new message
    call_args = graph.ainvoke.call_args
    msgs = call_args[0][0]["messages"]
    assert len(msgs) == 1
    assert msgs[0].content == "Nuovo messaggio"


@pytest.mark.asyncio
async def test_delete_checkpoint_returns_204():
    """DELETE /checkpoints/{id} should return 204 regardless of thread existence."""
    from chat_orchestrator.main import app
    from httpx import AsyncClient, ASGITransport

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.delete("/checkpoints/nonexistent-thread")
        assert resp.status_code == 204
```

- [ ] **Step 2: Run tests**

```bash
uv run pytest packages/chat-orchestrator/tests/test_checkpoint_recovery.py -v
```

- [ ] **Step 3: Commit**

```bash
git add packages/chat-orchestrator/tests/test_checkpoint_recovery.py
git commit -m "test(orchestrator): add checkpoint recovery and delete tests"
```

---

### Task 12: Tests — Frontend E2E

**Files:**
- Modify: `frontend/e2e/`

- [ ] **Step 1: Write E2E tests**

Test scenarios:
- Create new conversation → appears in sidebar
- Send message → persists after page refresh
- Delete conversation → removed from sidebar
- Reconnect after disconnect → history still visible

(Locate existing E2E test file and add scenarios following Playwright conventions.)

- [ ] **Step 2: Run tests**

```bash
cd frontend && npx playwright test e2e/chat-persistence.spec.ts
```

- [ ] **Step 3: Commit**

```bash
git add frontend/e2e/
git commit -m "test(e2e): add chat persistence scenarios"
```
