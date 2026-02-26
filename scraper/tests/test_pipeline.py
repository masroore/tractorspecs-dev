"""Tests for pipeline.py DB operations.

These tests require a live PostgreSQL connection. Set DATABASE_URL in the
environment or they will be skipped automatically.
"""

from __future__ import annotations

import os

import pytest

pytestmark = pytest.mark.skipif(
    not os.getenv("DATABASE_URL"),
    reason="DATABASE_URL not set — skipping pipeline DB tests",
)

pytestmark = pytest.mark.asyncio


async def _get_connection():
    import asyncpg

    dsn = os.environ["DATABASE_URL"]
    return await asyncpg.connect(dsn)


@pytest.fixture
async def conn():
    """Provide a transaction-wrapped connection that rolls back after each test."""
    import asyncpg

    dsn = os.environ["DATABASE_URL"]
    connection = await asyncpg.connect(dsn)
    tr = connection.transaction()
    await tr.start()
    yield connection
    await tr.rollback()
    await connection.close()


class TestUpsertManufacturer:
    async def test_returns_id_on_insert(self, conn) -> None:
        from pipeline import upsert_manufacturer

        mfr_id = await upsert_manufacturer(
            conn, {"name": "TestCo", "slug": "testco", "url": "/tractors/testco/"}
        )
        assert isinstance(mfr_id, int)
        assert mfr_id > 0

    async def test_idempotent(self, conn) -> None:
        from pipeline import upsert_manufacturer

        data = {
            "name": "IdempotentCo",
            "slug": "idempotentco",
            "url": "/tractors/idempotentco/",
        }
        id1 = await upsert_manufacturer(conn, data)
        id2 = await upsert_manufacturer(conn, data)
        assert id1 == id2


class TestUpsertSeries:
    async def test_returns_id(self, conn) -> None:
        from pipeline import upsert_manufacturer, upsert_series

        mfr_id = await upsert_manufacturer(
            conn, {"name": "SeriesCo", "slug": "seriesco", "url": "/tractors/seriesco/"}
        )
        series_id = await upsert_series(
            conn,
            mfr_id,
            {"name": "100 Series", "slug": "100-series", "models": []},
        )
        assert isinstance(series_id, int)
        assert series_id > 0

    async def test_idempotent(self, conn) -> None:
        from pipeline import upsert_manufacturer, upsert_series

        mfr_id = await upsert_manufacturer(
            conn,
            {"name": "SeriesCo2", "slug": "seriesco2", "url": "/tractors/seriesco2/"},
        )
        data = {"name": "200 Series", "slug": "200-series", "models": []}
        id1 = await upsert_series(conn, mfr_id, data)
        id2 = await upsert_series(conn, mfr_id, data)
        assert id1 == id2


class TestUpsertModel:
    async def test_returns_id_and_needs_update_on_first_insert(self, conn) -> None:
        from pipeline import upsert_manufacturer, upsert_model, upsert_series

        mfr_id = await upsert_manufacturer(
            conn, {"name": "ModelCo", "slug": "modelco", "url": "/tractors/modelco/"}
        )
        series_id = await upsert_series(
            conn, mfr_id, {"name": "M Series", "slug": "m-series", "models": []}
        )
        model_data = {
            "name": "ModelCo M1",
            "slug": "modelco-m1",
            "production_start_year": 2010,
            "production_end_year": 2020,
            "description": "A test tractor.",
            "horsepower_hp": 50.0,
            "content_hash": None,
        }
        model_id, needs_update = await upsert_model(conn, mfr_id, series_id, model_data)
        assert isinstance(model_id, int)
        assert needs_update is True

    async def test_no_update_when_hash_unchanged(self, conn) -> None:
        from pipeline import (
            replace_model_specs,
            upsert_manufacturer,
            upsert_model,
            upsert_series,
        )

        mfr_id = await upsert_manufacturer(
            conn, {"name": "HashCo", "slug": "hashco", "url": "/tractors/hashco/"}
        )
        series_id = await upsert_series(
            conn, mfr_id, {"name": "H Series", "slug": "h-series", "models": []}
        )
        test_hash = "abc123def456" * 4  # 48-char fake hash (pad to 64 if needed)
        test_hash = test_hash[:64].ljust(64, "0")
        model_data = {
            "name": "HashCo H1",
            "slug": "hashco-h1",
            "production_start_year": None,
            "production_end_year": None,
            "description": "",
            "horsepower_hp": None,
            "content_hash": test_hash,
        }
        model_id, _ = await upsert_model(conn, mfr_id, series_id, model_data)
        specs = [
            {
                "group": "Engine",
                "key": "HP",
                "value": "50",
                "unit": "hp",
                "display_order": 0,
            }
        ]
        await replace_model_specs(conn, model_id, specs, test_hash)

        # Second upsert with same hash — should return needs_update=False
        _, needs_update = await upsert_model(
            conn, mfr_id, series_id, {**model_data, "content_hash": test_hash}
        )
        assert needs_update is False


class TestReplaceModelSpecs:
    async def test_deletes_old_specs_before_insert(self, conn) -> None:
        from pipeline import (
            replace_model_specs,
            upsert_manufacturer,
            upsert_model,
            upsert_series,
        )

        mfr_id = await upsert_manufacturer(
            conn, {"name": "SpecCo", "slug": "specco", "url": "/tractors/specco/"}
        )
        series_id = await upsert_series(
            conn, mfr_id, {"name": "S Series", "slug": "s-series", "models": []}
        )
        model_data = {
            "name": "SpecCo S1",
            "slug": "specco-s1",
            "production_start_year": None,
            "production_end_year": None,
            "description": "",
            "horsepower_hp": None,
            "content_hash": None,
        }
        model_id, _ = await upsert_model(conn, mfr_id, series_id, model_data)

        first_specs = [
            {
                "group": "Engine",
                "key": "HP",
                "value": "50",
                "unit": "hp",
                "display_order": 0,
            }
        ]
        await replace_model_specs(conn, model_id, first_specs, "hash_v1".ljust(64, "0"))

        second_specs = [
            {
                "group": "Engine",
                "key": "HP",
                "value": "60",
                "unit": "hp",
                "display_order": 0,
            },
            {
                "group": "Engine",
                "key": "Cylinders",
                "value": "4",
                "unit": None,
                "display_order": 1,
            },
        ]
        await replace_model_specs(
            conn, model_id, second_specs, "hash_v2".ljust(64, "0")
        )

        rows = await conn.fetch(
            "SELECT key, value FROM model_specifications WHERE model_id = $1", model_id
        )
        assert len(rows) == 2
        values_by_key = {r["key"]: r["value"] for r in rows}
        assert values_by_key["HP"] == "60"
        assert values_by_key["Cylinders"] == "4"
