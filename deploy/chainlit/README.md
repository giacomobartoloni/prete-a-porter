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

Accounts are provisioned by an operator. Chainlit ships **no signup**: no
registration form, no registration route and no flag to enable (its login page
offers email + password and the configured OAuth providers, nothing else), so
`scripts/create_user.py` is the only account-creation path. It stores a bcrypt
hash in the Chainlit user metadata.

Create or update an account (stack running, from the repository root):

```bash
docker compose -f docker-compose.yml -f deploy/chainlit/docker-compose.chainlit.yml \
  exec prete-chat uv run python scripts/create_user.py --email don@example.com --name "Don Mario"
```

The password is read from the prompt (`getpass`), so it never lands in the shell
history or the process list. Do **not** add `-T` to `exec`: without a TTY the
prompt degrades.

Non-interactive variant — convenient in scripts, but the password stays in the
shell history and in the process list:

```bash
docker compose -f docker-compose.yml -f deploy/chainlit/docker-compose.chainlit.yml \
  exec prete-chat uv run python scripts/create_user.py \
  --email don@example.com --name "Don Mario" --password 'the-password'
```

Semantics:

- `--email` is the login identifier, normalised with `strip().lower()`; `--name`
  is the display name. An empty password is rejected (`Password must not be
  empty.`).
- Idempotent: when the identifier exists, the command updates its name and hash
  and prints `User … updated.` — this is also how a password is **reset**
  (re-run with the same email). Otherwise it prints `User … created.`
- Storage: one row in `users` (UUID, unique `identifier`) with
  `metadata = {"name": …, "password_hash": "<bcrypt cost 10>"}`. Cost 10 matches
  the legacy frontend, so hashes stay portable.
- Login: the `password_auth` callback in
  `packages/prete-chat/src/prete_chat/auth.py`. An unknown user and a wrong
  password both return `None`, so the login page cannot be used to enumerate
  accounts.
- Runtime requirements: `DATABASE_URL=postgresql+asyncpg://…` (the overlay sets
  it) and a non-empty `CHAINLIT_AUTH_SECRET`; without the secret the service
  fails at startup with `ConfigurationError`.
- The database publishes no port, so provisioning goes through `exec`; running
  the script from the host would first require publishing it.

Verification:

```bash
docker compose -f docker-compose.yml -f deploy/chainlit/docker-compose.chainlit.yml \
  exec prete-chat-db psql -U chainlit -d chainlit \
  -c "select identifier, metadata->>'name' as name from users;"
```

`users` has no `display_name` column — the name lives in `metadata`. Deleting a
row from `users` cascades through `threads` and from there to `steps`,
`elements` and `feedbacks` (`ON DELETE CASCADE` in `init.sql`).

Then sign in at <http://localhost:3003> with the email and password.

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
