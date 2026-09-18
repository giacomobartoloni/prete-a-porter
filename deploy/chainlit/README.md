# Chainlit native UI — deployment and operations

Additive Compose overlay for the native Prête-à-Porter UI (`packages/prete-chat`).
The base stack (orchestrator, agents, OpenWebUI, LibreChat, legacy frontend) is
not modified.

```bash
# Development / evaluation (from the repository root)
docker compose -f docker-compose.yml -f deploy/chainlit/docker-compose.chainlit.yml up -d --build

# Native UI
open http://localhost:3003
```

| Service | Image | Port | Notes |
|---|---|---|---|
| `prete-chat` | built from `packages/prete-chat/Dockerfile` | `127.0.0.1:3003` | Chainlit 2.12.0; imports the chat core in-process |
| `prete-chat-db` | `postgres:17.6-alpine` (pinned minor) | none | conversation store; internal network only |

## Environment

| Variable | Where | Purpose |
|---|---|---|
| `PRETE_CHAT_DB_PASSWORD` | `.env` | password of the `chainlit` PostgreSQL role; also embedded in the service's `DATABASE_URL` |
| `CHAINLIT_AUTH_SECRET` | `.env` | signs the session cookie (`openssl rand -hex 32`). Rotating it logs everyone out |
| `CHAINLIT_URL` | `.env` / overlay | public URL, for cookie and redirect correctness behind Caddy |
| `DATABASE_URL` | overlay (per service) | `postgresql+asyncpg://chainlit:…@prete-chat-db:5432/chainlit`. The repository `.env` value targets the legacy frontend and is overridden here |

Persistence is opt-in in code: only a `postgresql+asyncpg://` URL enables the data
layer and password authentication. Unsetting it (rollback to the POC) leaves the
service running without history and without login.

## Users

Chainlit has no stock signup; accounts are provisioned by an operator:

```bash
docker compose -f docker-compose.yml -f deploy/chainlit/docker-compose.chainlit.yml \
  exec prete-chat uv run python scripts/create_user.py --email don@example.com --name "Don Mario"
```

Passwords are stored as bcrypt hashes (cost 10) in the Chainlit user metadata,
the same cost the legacy frontend used. Re-running the command updates the name
and password of an existing account.

## Schema and upgrades

- First boot applies `deploy/chainlit/init.sql` (mounted into
  `/docker-entrypoint-initdb.d`). It is idempotent (`CREATE TABLE IF NOT EXISTS`).
- The schema follows Chainlit's SQLAlchemy data layer DDL, including the columns
  added after 2.0: `steps.command` (2.1.0), `steps.defaultOpen` (2.3.0),
  `steps.modes` (2.9.4), plus `steps.autoCollapse`, which the 2.12.0 code writes
  but the published DDL does not list yet (its absence silently drops tool-step
  inserts: `UndefinedColumnError`). When the docs and the shipped code disagree,
  the code wins; check `Step.to_dict()` in the pinned release.
- **Upgrade procedure (no migration framework):** read the pinned release's
  migration guide → apply the listed `ALTER`s to the database → deploy the new
  image. `docker-entrypoint-initdb.d` runs only on an empty data directory, so an
  existing database needs the manual `psql -f` step. For this release:

  ```sql
  ALTER TABLE steps ADD COLUMN IF NOT EXISTS "autoCollapse" BOOLEAN;
  ```

## Backup and restore

```bash
# Backup
docker compose -f docker-compose.yml -f deploy/chainlit/docker-compose.chainlit.yml \
  exec prete-chat-db pg_dump -U chainlit chainlit > chainlit-$(date +%F).sql

# Restore (empty database)
docker compose -f docker-compose.yml -f deploy/chainlit/docker-compose.chainlit.yml \
  exec -T prete-chat-db psql -U chainlit -d chainlit < chainlit-2026-09-18.sql
```

Conversation content and feedback live in this database and in any backups;
deleting a thread from the UI cascades to its steps, elements and feedback rows.
Retention is an owner decision (plan §29).
