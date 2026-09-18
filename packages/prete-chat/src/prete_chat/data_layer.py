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

from chainlit.data.sql_alchemy import SQLAlchemyDataLayer

from prete_chat import config


class SerializedSQLAlchemyDataLayer(SQLAlchemyDataLayer):
    """SQLAlchemy data layer whose statements never run concurrently."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._statement_lock = asyncio.Lock()

    async def execute_sql(self, query: str, parameters: dict) -> Any:
        async with self._statement_lock:
            return await super().execute_sql(query, parameters)


def build() -> SerializedSQLAlchemyDataLayer | None:
    """Build the data layer from the environment, or ``None`` when disabled."""
    url = config.database_url()
    if url is None:
        return None
    return SerializedSQLAlchemyDataLayer(conninfo=url)
