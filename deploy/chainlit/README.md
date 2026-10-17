# Chainlit native UI — deployment and operations

Additive Compose overlay for the native Prête-à-Porter UI (`packages/prete-chat`).
The base stack (orchestrator, agents, OpenWebUI and the legacy frontend) is
not modified. The LibreChat overlay, when enabled separately, is also unaffected.

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
| `OAUTH_GOOGLE_CLIENT_ID` / `OAUTH_GOOGLE_CLIENT_SECRET` | `.env` | optional Google OAuth Web application credentials; both required together |
| `PRETE_CHAT_GOOGLE_ALLOWED_EMAILS` | `.env` | explicit comma-separated invited emails; required with Google credentials; compared after trim/lowercase |

Persistence is opt-in in code: only a `postgresql+asyncpg://` URL enables the data
layer and password authentication. Unsetting it (rollback to the POC) leaves the
service running without history and without login.

## Users

Password accounts are provisioned by an operator through `scripts/create_user.py`,
which stores a bcrypt hash in user metadata. Optional Google login lets explicitly
invited users create their account on first sign-in. Chainlit has no separate
registration form.

The bcrypt `password_hash` is persisted server-side in user metadata. The
`SerializedSQLAlchemyDataLayer.get_user()` getter is a public/session-safe read
that strips `password_hash`; `get_user_for_auth()` is the dedicated raw,
auth-only read used by the password verification callback. Keep these getters
separate: Chainlit reloads the persisted user when resolving authenticated
sessions and serving `GET /user`. Returning raw metadata from the public getter
would expose the credential verifier through session metadata or `/user`;
passing it into the session user would also expose it in the JWT.

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

## Optional Google login

The native UI uses [Chainlit's built-in OAuth flow](https://docs.chainlit.io/authentication/oauth).
The agents and `/v1` API keep their existing authentication.

1. Create a Google Cloud OAuth client of type **Web application** and configure
   the consent screen for the intended audience. For testing, configure the
   Google-side test audience as required by your Cloud project.
2. Register the exact redirect URI `http://localhost:3003/auth/oauth/google/callback`
   for local use, or `https://<your-host>/auth/oauth/google/callback` for production.
   Set `CHAINLIT_URL` to the matching origin. Public deployments require HTTPS;
   HTTP is accepted only for localhost/loopback. Subpath deployment is not supported
   by this integration.
3. Set both `OAUTH_GOOGLE_CLIENT_ID` and `OAUTH_GOOGLE_CLIENT_SECRET`, then set
   `PRETE_CHAT_GOOGLE_ALLOWED_EMAILS=don@example.com,another@example.com` in `.env`.
   The overlay already loads this file. Credentials, callback URL and invitation
   list must be configured before starting the service; incomplete setup fails
   startup. Empty credentials retain password-only operation.
4. Recreate `prete-chat` with the overlay and sign in with an invited Google
   account. Check `GET /auth/config` advertises `google` and that the login page
   offers Google alongside the password form.
5. Verify an uninvited account is rejected. For an existing password account,
   sign in with Google, then with its original password, and reopen its history.

The callback requires Google's `verified_email` boolean and stable user `id`.
It rejects every other provider and never stores access tokens. A first allowed
login creates a user; a matching normalized email links to the existing account,
preserving its UUID, history, quota key and server-side password hash. The stored
Google subject must match on subsequent Google logins, including after a password
login. Public user responses never include the password hash.

The email invitation list is intentionally explicit: no wildcards, domain suffix
matching or automatic admission of all Google accounts. Removing an invitation
blocks future Google logins; it does **not** revoke already issued sessions or
disable a separately provisioned password. Rotate `CHAINLIT_AUTH_SECRET` if all
sessions must be invalidated.

Google Cloud credentials, DNS and public routing are operator configuration.
Unit tests and PostgreSQL callback tests cannot establish that a real Google
browser roundtrip or the production proxy is configured correctly.

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
