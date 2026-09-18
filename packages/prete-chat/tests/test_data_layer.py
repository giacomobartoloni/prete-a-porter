"""The data layer serializes every statement; concurrent writes must not race.

Regression guard for the live defect: Chainlit schedules step/message writes as
independent tasks, and the bundled layer's fresh-session-per-statement pattern
interleaved ``session.begin()`` calls on asyncpg until writes were dropped
(persisted answers with empty output, missing tool steps).
"""

import asyncio

from chainlit.data.sql_alchemy import SQLAlchemyDataLayer

from prete_chat.data_layer import SerializedSQLAlchemyDataLayer, build


class TestBuild:
    def test_no_url_builds_nothing(self, monkeypatch):
        monkeypatch.delenv("DATABASE_URL", raising=False)
        assert build() is None

    def test_postgres_url_builds_the_serialized_layer(self, monkeypatch):
        monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://chainlit:pw@prete-chat-db:5432/chainlit")
        layer = build()
        try:
            assert isinstance(layer, SerializedSQLAlchemyDataLayer)
        finally:
            asyncio.run(layer.close())


class TestStatementSerialization:
    def test_concurrent_statements_never_overlap(self, monkeypatch):
        layer = SerializedSQLAlchemyDataLayer(conninfo="postgresql+asyncpg://chainlit:pw@localhost:5432/chainlit")
        overlap = {"now": 0, "max": 0}

        async def probe(self, query, parameters):
            overlap["now"] += 1
            overlap["max"] = max(overlap["max"], overlap["now"])
            await asyncio.sleep(0.01)
            overlap["now"] -= 1
            return None

        monkeypatch.setattr(SQLAlchemyDataLayer, "execute_sql", probe)

        async def run() -> None:
            await asyncio.gather(*(layer.execute_sql("SELECT 1", {}) for _ in range(5)))
            await layer.close()

        asyncio.run(run())
        assert overlap["max"] == 1
