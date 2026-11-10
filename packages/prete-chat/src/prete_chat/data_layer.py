"""Chainlit data layer: PostgreSQL for users, threads, steps and feedback.

The bundled SQLAlchemy data layer is the one Chainlit documents for Postgres;
the schema lives in ``deploy/chainlit/init.sql`` and the operations procedure in
``deploy/chainlit/README.md``. This module wraps it for four reasons:

1. Chainlit fires every step/message write as a separate ``asyncio`` task, and
   the bundled layer's one-fresh-session-per-statement pattern races on that
   workload: concurrent ``session.begin()`` calls surface asyncpg's
   ``cannot use Connection.transaction() in a manually started transaction``
   and the write is dropped (observed live: persisted assistant messages with
   empty output, missing tool steps). Serializing the statement executor removes
   the race; at this service's write volume the lock costs nothing, and every
   query in the layer funnels through ``execute_sql``.
2. Construction from the environment belongs to this service, so tests and the
   provisioning script build the same object the app registers.
3. Credential metadata must stay server-side: Chainlit's ``authenticate_user``
   returns ``data_layer.get_user()`` from ``/user``, so the public getter must
   never expose ``password_hash``. Auth reads use ``get_user_for_auth``.
4. PostgreSQL atomically merges login profiles and guards the Google subject,
   preserving credentials and bindings even across concurrent processes.
"""

import asyncio
import json
import uuid
from datetime import UTC, datetime
from typing import Any

import chainlit as cl
from chainlit.data.sql_alchemy import SQLAlchemyDataLayer
from chainlit.user import PersistedUser

from prete_chat import auth, config


def _sanitize_persisted_user(user: PersistedUser) -> PersistedUser:
    """Return a copy of ``user`` without credential metadata (never mutate in place)."""
    metadata = dict(user.metadata or {})
    metadata.pop(auth.PASSWORD_METADATA_KEY, None)
    return PersistedUser(
        id=user.id,
        identifier=user.identifier,
        createdAt=user.createdAt,
        display_name=user.display_name,
        metadata=metadata,
    )


class SerializedSQLAlchemyDataLayer(SQLAlchemyDataLayer):
    """SQLAlchemy data layer whose statements never run concurrently.

    Also keeps the bcrypt password hash server-side: Chainlit's login path
    persists the session ``User`` via ``create_user``, and a sanitized
    client-visible ``User`` (no ``password_hash``) would otherwise wipe the
    credential verifier on every successful login.

    ``get_user()`` is a public/session-safe read because Chainlit returns its
    result from ``/user``. Credential metadata must only be read via
    ``get_user_for_auth()``.
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._statement_lock = asyncio.Lock()
        self._owner_loop: asyncio.AbstractEventLoop | None = None

    async def execute_sql(self, query: str, parameters: dict) -> Any:
        loop = asyncio.get_running_loop()
        # The first server query (authentication/history) owns the pool. Later
        # callback threads must use that same loop, including its lock.
        if self._owner_loop is None:
            self._owner_loop = loop
        if loop is not self._owner_loop:
            if self._owner_loop.is_closed() or not self._owner_loop.is_running():
                raise RuntimeError("The database owner event loop is unavailable")
            future = asyncio.run_coroutine_threadsafe(self.execute_sql(query, parameters), self._owner_loop)
            return await asyncio.wrap_future(future)
        async with self._statement_lock:
            return await super().execute_sql(query, parameters)

    async def get_user(self, identifier: str) -> PersistedUser | None:
        """Public/session-safe read: never includes ``password_hash``."""
        persisted = await super().get_user(identifier)
        if persisted is None:
            return None
        return _sanitize_persisted_user(persisted)

    async def get_user_for_auth(self, identifier: str) -> PersistedUser | None:
        """Private auth-only read: may include ``password_hash`` in metadata.

        Must not be used for session/JWT/``/user`` responses.
        """
        return await super().get_user(identifier)

    async def create_step(self, step_dict: dict) -> Any:
        """Progress is ephemeral UI, never canonical conversation history."""
        if (step_dict.get("metadata") or {}).get("transient_progress"):
            return True
        return await super().create_step(step_dict)

    async def update_step(self, step_dict: dict) -> Any:
        if (step_dict.get("metadata") or {}).get("transient_progress"):
            return True
        return await super().update_step(step_dict)

    async def create_user(self, user: cl.User) -> PersistedUser | None:
        """Atomically merge a profile, retaining credentials and Google binding.

        PostgreSQL owns concurrency across processes and provisioning commands.
        A conflicting Google subject or SQL failure returns ``None``. The OAuth
        callback checks this before allowing Chainlit to issue a session.
        """
        rows = await self.execute_sql(
            query="""
                INSERT INTO users ("id", "identifier", "createdAt", "metadata")
                VALUES (:id, :identifier, :created_at, CAST(:metadata AS JSONB))
                ON CONFLICT ("identifier") DO UPDATE
                SET "metadata" = users."metadata" || EXCLUDED."metadata"
                WHERE users."metadata"->>'google_id' IS NULL
                   OR EXCLUDED."metadata"->>'google_id' IS NULL
                   OR users."metadata"->>'google_id' = EXCLUDED."metadata"->>'google_id'
                RETURNING "id", "identifier", "createdAt", "metadata"
            """,
            parameters={
                "id": str(uuid.uuid4()),
                "identifier": user.identifier,
                "created_at": datetime.now(UTC).isoformat(),
                "metadata": json.dumps(user.metadata or {}),
            },
        )
        if not isinstance(rows, list) or not rows:
            return None
        return _sanitize_persisted_user(PersistedUser(**rows[0]))


def build() -> SerializedSQLAlchemyDataLayer | None:
    """Build the data layer from the environment, or ``None`` when disabled."""
    url = config.database_url()
    if url is None:
        return None
    return SerializedSQLAlchemyDataLayer(conninfo=url)
