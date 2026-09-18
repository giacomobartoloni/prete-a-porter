# LibreChat as a Prête-à-Porter client

LibreChat is a **second chat shell** for the existing agent runtime, added
alongside OpenWebUI and the legacy Next.js frontend. It owns generic chat
concerns — accounts, conversation persistence, history, message rendering — and
talks to the chat-orchestrator through the same authenticated
OpenAI-compatible surface every other client uses.

```
LibreChat ─┐
OpenWebUI ─┼── POST /v1/chat/completions ──▶ chat-orchestrator ──A2A──▶ agents
curl/SDK  ─┘        (ORCHESTRATOR_API_KEY)
```

Nothing about the A2A protocol, the LangGraph runtime, the homily agent, or its
ChromaDB corpus changes. The browser never holds the orchestrator credential:
LibreChat's backend makes the call.

## Files

| File | Purpose |
|---|---|
| `librechat.yaml` | Endpoint config, mounted read-only at `/app/librechat.yaml` |
| `docker-compose.librechat.yml` | Additive Compose overlay: `librechat` + `librechat-mongodb` |

## Pinned release

LibreChat is pinned to **v0.8.7** (`LIBRECHAT_IMAGE_TAG`). The `version:` field
in `librechat.yaml` (`1.3.13`) matches that release's config schema.

To upgrade: change the tag, pull the release's `librechat.example.yaml`, diff the
schema against this file, start the container, and confirm LibreChat boots
without a config-validation error before merging. Do not run `latest`.

## Setup

1. Add the LibreChat secrets to `.env` (names in `.env.example`):

   ```bash
   openssl rand -hex 32   # LIBRECHAT_JWT_SECRET
   openssl rand -hex 32   # LIBRECHAT_JWT_REFRESH_SECRET
   openssl rand -hex 32   # LIBRECHAT_CREDS_KEY
   openssl rand -hex 16   # LIBRECHAT_CREDS_IV
   ```

2. Start the overlay:

   ```bash
   docker compose -f docker-compose.yml -f deploy/librechat/docker-compose.librechat.yml up -d
   ```

   This leaves the base stack untouched: `liturgy-agent`, `homily-agent`,
   `chat-orchestrator`, `openwebui`, `frontend`, and `caddy` keep running.

3. Open `http://localhost:3002`, register the first account (it becomes the
   admin), and send *"Quali sono le letture di domenica prossima?"*.

4. Production: point `librechat.prete-a-porter.dev` at the server, set
   `LIBRECHAT_DOMAIN_CLIENT` / `LIBRECHAT_DOMAIN_SERVER` to
   `https://librechat.prete-a-porter.dev`, and uncomment the `librechat` site
   block in the root `Caddyfile`.

## What LibreChat is allowed to own

| Concern | Owner |
|---|---|
| Accounts, sessions, registration | LibreChat |
| Conversation and message persistence (MongoDB) | LibreChat |
| Conversation list, history, reopen, titles | LibreChat |
| Streaming rendering, markdown, responsive layout | LibreChat |
| Orchestration, tool selection, A2A calls | chat-orchestrator |
| Liturgical data, homily generation, RAG | liturgy/homily agents |
| Per-user quota, thread correlation | chat-orchestrator (from forwarded headers) |

There is **one** canonical conversation store: LibreChat's MongoDB. The
orchestrator is stateless per request — it rebuilds the message list from the
request body and does not persist a second history.

## Identity and headers

`librechat.yaml` forwards, on every request:

| Header | Value | Used by the orchestrator for |
|---|---|---|
| `X-User-ID` | `{{LIBRECHAT_USER_ID}}` | Per-user rate-limit key |
| `X-User-Email` | `{{LIBRECHAT_USER_EMAIL}}` | Log correlation (optional) |
| `X-Conversation-ID` | `{{LIBRECHAT_BODY_CONVERSATIONID}}` | Thread correlation (`conversation_id` in logs) |
| `X-Message-ID` | `{{LIBRECHAT_BODY_MESSAGEID}}` | Trace correlation |
| `X-Parent-Message-ID` | `{{LIBRECHAT_BODY_PARENTMESSAGEID}}` | Accepted, not read |

The orchestrator trusts these headers only because the request also carries a
valid `ORCHESTRATOR_API_KEY`, which only server-side clients hold. LibreChat
reuses the existing `ORCHESTRATOR_API_KEY`; there is no second credential to
rotate.

## What is disabled, and why

| LibreChat feature | State | Reason |
|---|---|---|
| Model selector | off | Single model; the legacy UI and OpenWebUI behave the same way |
| Parameter panel | off | `temperature`, `top_p` are ignored by the adapter; homily preferences are domain parameters, not sampling parameters |
| Presets, prompts, bookmarks, multi-conversation | off | Not part of the product; keeps the composer minimal |
| Memory | off | Would create a second memory system beside the agents |
| Web search, file search, file citations, RAG | off | The homily agent's corpus is the only retrieval source; user uploads do not influence it |
| Agents / MCP | off | Prête's tools live in the orchestrator; duplicating them in LibreChat would fork the domain logic |
| Conversation titles | off (`titleConvo: false`) | Title generation would invoke the full homily ReAct loop for a one-line string |
| Conversation search | off (`SEARCH=false`) | Needs Meilisearch, which is not deployed |

Titles therefore stay at LibreChat's default placeholder until a cheap title
model is configured. Do not point `titleModel` at `prete-a-porter`.

## Verification checklist

Run these against a started stack; they are the level-2/3 checks that matter for
this boundary.

```bash
# 1. Compose parses and the new containers exist
docker compose -f docker-compose.yml -f deploy/librechat/docker-compose.librechat.yml config > /dev/null
docker compose -f docker-compose.yml -f deploy/librechat/docker-compose.librechat.yml ps

# 2. LibreChat started with a valid config (no zod schema error)
docker logs librechat 2>&1 | tail -20

# 3. The endpoint is reachable from inside the LibreChat container
docker exec librechat node -e "fetch('http://chat-orchestrator:8000/v1/models',{headers:{Authorization:'Bearer '+process.env.ORCHESTRATOR_API_KEY}}).then(r=>r.text()).then(console.log)"

# 4. One chat turn carries the identity headers
docker compose logs chat-orchestrator | grep "Chat completion received"
#    Look for conversation_id, user_id, stream=true, model=prete-a-porter
```

Then, in the UI: register, send a homily request, refresh the page, reopen the
conversation, and continue it. The orchestrator log must show two requests with
the same `conversation_id` and the same `user_id`. A second account must produce
a different `user_id` and must not see the first account's conversations.

Restart `chat-orchestrator`; the conversation must remain intact in LibreChat
(it is LibreChat's data, not the orchestrator's).

### Observed results (2026-09-18, first run)

| Check | Result |
|---|---|
| Container boot with the pinned config | OK; role permissions applied for every disabled feature |
| `/v1/models` from inside the container | `200`, model card |
| Turn 1: *"Quali sono le letture di domenica prossima?"* | readings retrieved and streamed; one request, `outcome=completed` |
| Identity headers | `user_id`, `conversation_id`, `message_id` all present in the boundary log |
| Conversation id across three turns | stable |
| Second user | distinct `user_id` and `conversation_id`; empty conversation list |
| Auxiliary requests | none — POST count equals turn count |
| Orchestrator restart | conversation reopened with history intact |
| `CHAT_REQUEST_TIMEOUT_SECONDS=5` | `outcome=timeout`; UI showed the Italian error; the stream closed cleanly |
| Restore to 180 s | next turn completed, same conversation |

Full detail, including the reproduction commands, is in
[`docs/verification-levels.md`](../../docs/verification-levels.md).

## Rollback

```bash
docker compose -f docker-compose.yml -f deploy/librechat/docker-compose.librechat.yml down
```

Removing the overlay touches nothing else: OpenWebUI, the legacy frontend, the
agents, and the RAG corpus are untouched. MongoDB data lives in the
`deploy_librechat_mongo_data` volume; delete it only when abandoning the pilot.

## Known gaps

- **Token accounting is zero.** The adapter does not surface provider token
  counts, so `usage` is reported as zeros. LibreChat may display zero tokens.
- **No file-upload path.** Uploads are not wired to the homily agent's corpus;
  enabling them requires an explicit ingestion contract first.
- **Rich agent activity is not represented.** Tool/agent progress is not exposed
  through the OpenAI-compatible contract; the chat shows text only.
- **Whitespace-level title gap.** With `titleConvo: false`, conversations keep
  the default title until renamed manually.

## License

LibreChat is MIT-licensed; this repository is AGPL-3.0. The pinned upstream image
is used unmodified — no LibreChat source is vendored here. If a customized fork
is ever distributed, keep upstream notices intact and review the license terms
for the deployment model. This note is engineering context, not legal advice.
