"""Chainlit data layer: PostgreSQL for users, threads, steps and feedback.

The bundled SQLAlchemy data layer is the one Chainlit documents for Postgres;
the schema lives in ``deploy/chainlit/init.sql`` and the operations procedure in
``deploy/chainlit/README.md``. This module wraps it for two reasons:

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
"""

import asyncio
from typing import Any

import chainlit as cl
from chainlit.data.sql_alchemy import SQLAlchemyDataLayer
from chainlit.user import PersistedUser

from prete_chat import auth, config


class SerializedSQLAlchemyDataLayer(SQLAlchemyDataLayer):
    """SQLAlchemy data layer whose statements never run concurrently.

    Also keeps the bcrypt password hash server-side: Chainlit's login path
    persists the session ``User`` via ``create_user``, and a sanitized
    client-visible ``User`` (no ``password_hash``) would otherwise wipe the
    credential verifier on every successful login.
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._statement_lock = asyncio.Lock()

    async def execute_sql(self, query: str, parameters: dict) -> Any:
        async with self._statement_lock:
            return await super().execute_sql(query, parameters)

    async def create_user(self, user: cl.User) -> PersistedUser | None:
        """Persist ``user`` without dropping an existing password hash.

        Must not mutate ``user.metadata`` in place: that same object is used to
        build the session JWT.
        """
        existing = await super().get_user(user.identifier)
        metadata = dict(user.metadata or {})
        if existing is not None:
            existing_metadata = existing.metadata or {}
            stored_hash = existing_metadata.get(auth.PASSWORD_METADATA_KEY)
            if (
                isinstance(stored_hash, str)
                and auth.PASSWORD_METADATA_KEY not in metadata
            ):
                metadata[auth.PASSWORD_METADATA_KEY] = stored_hash
        persistence_user = cl.User(
            identifier=user.identifier,
            display_name=user.display_name,
            metadata=metadata,
        )
        return await super().create_user(persistence_user)


def build() -> SerializedSQLAlchemyDataLayer | None:
    """Build the data layer from the environment, or ``None`` when disabled."""
    url = config.database_url()
    if url is None:
        return None
    return SerializedSQLAlchemyDataLayer(conninfo=url)
