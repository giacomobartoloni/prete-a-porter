"""Chainlit data layer: PostgreSQL for users, threads, steps and feedback.

The bundled SQLAlchemy data layer is the one Chainlit documents for Postgres;
the schema lives in ``deploy/chainlit/init.sql`` and the operations procedure in
``deploy/chainlit/README.md``. This module wraps it for three reasons:

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
"""

import asyncio
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

    async def execute_sql(self, query: str, parameters: dict) -> Any:
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

    async def create_user(self, user: cl.User) -> PersistedUser | None:
        """Persist ``user`` without dropping an existing password hash.

        Must not mutate ``user.metadata`` in place: that same object is used to
        build the session JWT. Uses ``super().get_user`` so the hash is still
        visible when re-injecting into the persistence path. The returned
        ``PersistedUser`` is sanitized for any caller that treats the return
        value as session-visible.
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
        result = await super().create_user(persistence_user)
        if result is None:
            return None
        return _sanitize_persisted_user(result)


def build() -> SerializedSQLAlchemyDataLayer | None:
    """Build the data layer from the environment, or ``None`` when disabled."""
    url = config.database_url()
    if url is None:
        return None
    return SerializedSQLAlchemyDataLayer(conninfo=url)
