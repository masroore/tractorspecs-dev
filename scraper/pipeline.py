from __future__ import annotations

import json
from typing import Any

import asyncpg

from logger import log
from transformer import build_slug, compute_spec_hash


# ---------------------------------------------------------------------------
# Manufacturers
# ---------------------------------------------------------------------------


async def upsert_manufacturer(conn: asyncpg.Connection, data: dict[str, Any]) -> int:
    """Insert or update a manufacturer row.  Returns the manufacturer id."""
    slug = data.get("slug") or build_slug(data["name"])

    row = await conn.fetchrow(
        """
        INSERT INTO manufacturers
            (slug, name, country, description, name_search, created_at, updated_at)
        VALUES
            ($1, $2, $3, $4, to_tsvector('english', $5), NOW(), NOW())
        ON CONFLICT (slug) DO UPDATE
            SET name        = EXCLUDED.name,
                country     = COALESCE(EXCLUDED.country, manufacturers.country),
                description = COALESCE(EXCLUDED.description, manufacturers.description),
                name_search = to_tsvector('english', $5),
                updated_at  = NOW()
        RETURNING id
        """,
        slug,
        data["name"],
        data.get("country"),
        data.get("description"),
        data["name"],  # $5 — text copy for to_tsvector
    )

    manufacturer_id = int(row["id"])
    log.debug("pipeline.upsert_manufacturer", id=manufacturer_id, slug=slug)
    return manufacturer_id


# ---------------------------------------------------------------------------
# Series
# ---------------------------------------------------------------------------


async def upsert_series(
    conn: asyncpg.Connection,
    manufacturer_id: int,
    data: dict[str, Any],
) -> int:
    """Insert or update a series row.  Returns the series id."""
    slug = data.get("slug") or build_slug(data["name"])

    row = await conn.fetchrow(
        """
        INSERT INTO series
            (manufacturer_id, slug, name, tractor_type,
             production_start_year, production_end_year,
             created_at, updated_at)
        VALUES
            ($1, $2, $3, $4, $5, $6, NOW(), NOW())
        ON CONFLICT (manufacturer_id, slug) DO UPDATE
            SET name                = EXCLUDED.name,
                tractor_type        = COALESCE(EXCLUDED.tractor_type, series.tractor_type),
                production_start_year = COALESCE(EXCLUDED.production_start_year,
                                                  series.production_start_year),
                production_end_year   = COALESCE(EXCLUDED.production_end_year,
                                                  series.production_end_year),
                updated_at          = NOW()
        RETURNING id
        """,
        manufacturer_id,
        slug,
        data["name"],
        data.get("tractor_type"),
        data.get("production_start") or data.get("production_start_year"),
        data.get("production_end") or data.get("production_end_year"),
    )

    series_id = int(row["id"])
    log.debug("pipeline.upsert_series", id=series_id, slug=slug)
    return series_id


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


async def upsert_model(
    conn: asyncpg.Connection,
    manufacturer_id: int,
    series_id: int | None,
    data: dict[str, Any],
) -> tuple[int, bool]:
    """Insert or update a tractor model.

    Returns (model_id, specs_need_update).
    specs_need_update is False when the content hash is unchanged —
    the caller should skip replace_model_specs() to avoid unnecessary work.
    """
    slug = data.get("slug") or build_slug(data["name"])
    new_hash = compute_spec_hash(data.get("specs", []))

    # Check existing hash to detect unchanged pages
    existing = await conn.fetchrow(
        "SELECT id, content_hash FROM tractor_models WHERE slug = $1",
        slug,
    )

    model_id: int
    if existing and existing["content_hash"] == new_hash:
        # Content unchanged — still upsert the row (timestamps etc.) but
        # signal the caller to skip spec replacement
        model_id = int(existing["id"])
        log.debug("pipeline.model_unchanged", id=model_id, slug=slug)
        return model_id, False

    row = await conn.fetchrow(
        """
        INSERT INTO tractor_models
            (manufacturer_id, series_id, slug, name, tractor_type,
             production_start_year, production_end_year,
             horsepower_hp, description, name_search,
             is_active, created_at, updated_at)
        VALUES
            ($1, $2, $3, $4, $5, $6, $7, $8, $9,
             to_tsvector('english', $10), TRUE, NOW(), NOW())
        ON CONFLICT (slug) DO UPDATE
            SET manufacturer_id       = EXCLUDED.manufacturer_id,
                series_id             = COALESCE(EXCLUDED.series_id, tractor_models.series_id),
                tractor_type          = COALESCE(EXCLUDED.tractor_type, tractor_models.tractor_type),
                production_start_year = COALESCE(EXCLUDED.production_start_year,
                                                  tractor_models.production_start_year),
                production_end_year   = COALESCE(EXCLUDED.production_end_year,
                                                  tractor_models.production_end_year),
                horsepower_hp         = COALESCE(EXCLUDED.horsepower_hp,
                                                  tractor_models.horsepower_hp),
                description           = COALESCE(EXCLUDED.description, tractor_models.description),
                name_search           = to_tsvector('english', $10),
                updated_at            = NOW()
        RETURNING id
        """,
        manufacturer_id,
        series_id,
        slug,
        data["name"],
        data.get("tractor_type"),
        data.get("production_start_year"),
        data.get("production_end_year"),
        data.get("horsepower_hp"),
        data.get("description"),
        data["name"],  # $10 — text copy for to_tsvector
    )

    model_id = int(row["id"])
    log.debug("pipeline.upsert_model", id=model_id, slug=slug, hash=new_hash)
    return model_id, True


# ---------------------------------------------------------------------------
# Specifications
# ---------------------------------------------------------------------------


async def replace_model_specs(
    conn: asyncpg.Connection,
    model_id: int,
    specs: list[dict[str, Any]],
    content_hash: str,
) -> None:
    """Replace all spec rows for a model and persist the new content_hash.

    Uses asyncpg's copy_records_to_table for fast bulk insert.
    """
    # Delete existing specs
    deleted = await conn.execute(
        "DELETE FROM model_specifications WHERE model_id = $1",
        model_id,
    )
    log.debug("pipeline.specs_deleted", model_id=model_id, deleted=deleted)

    if specs:
        records = [
            (
                model_id,
                spec["group"],
                spec["key"],
                spec.get("value"),
                spec.get("unit"),
                spec.get("display_order", idx),
            )
            for idx, spec in enumerate(specs)
        ]

        await conn.copy_records_to_table(
            "model_specifications",
            records=records,
            columns=[
                "model_id",
                "spec_group",
                "spec_key",
                "spec_value",
                "unit",
                "display_order",
            ],
        )

    # Persist content hash on the model row so future crawls can skip unchanged pages
    await conn.execute(
        "UPDATE tractor_models SET content_hash = $1 WHERE id = $2",
        content_hash,
        model_id,
    )

    log.debug("pipeline.specs_inserted", model_id=model_id, count=len(specs))


# ---------------------------------------------------------------------------
# Crawl target state management
# ---------------------------------------------------------------------------


async def enqueue_crawl_target(
    conn: asyncpg.Connection,
    url: str,
    target_type: str,
    meta: dict[str, Any] | None = None,
    parent_id: int | None = None,
) -> None:
    """Add a URL to crawl_targets if not already present (idempotent)."""
    await conn.execute(
        """
        INSERT INTO crawl_targets (url, type, meta, parent_id, status, created_at, updated_at)
        VALUES ($1, $2, $3, $4, 'pending', NOW(), NOW())
        ON CONFLICT (url) DO NOTHING
        """,
        url,
        target_type,
        json.dumps(meta or {}),
        parent_id,
    )


async def update_crawl_target_status(
    conn: asyncpg.Connection,
    url: str,
    status: str,
    content_hash: str | None = None,
    error: str | None = None,
) -> None:
    """Update the status (and optional hash/error) of a crawl target."""
    await conn.execute(
        """
        UPDATE crawl_targets
        SET status          = $2,
            content_hash    = COALESCE($3, content_hash),
            error_message   = $4,
            last_crawled_at = NOW(),
            updated_at      = NOW()
        WHERE url = $1
        """,
        url,
        status,
        content_hash,
        error,
    )


async def fetch_pending_targets(
    conn: asyncpg.Connection,
    target_type: str,
    batch_size: int = 50,
) -> list[asyncpg.Record]:
    """Fetch and lock a batch of pending crawl targets (SKIP LOCKED)."""
    rows = await conn.fetch(
        """
        SELECT id, url, meta, parent_id
        FROM   crawl_targets
        WHERE  status = 'pending'
          AND  type   = $1
        ORDER BY id
        LIMIT  $2
        FOR UPDATE SKIP LOCKED
        """,
        target_type,
        batch_size,
    )
    return list(rows)


async def mark_targets_in_progress(
    conn: asyncpg.Connection,
    urls: list[str],
) -> None:
    """Bulk-mark a list of URLs as in_progress."""
    await conn.execute(
        "UPDATE crawl_targets SET status='in_progress', updated_at=NOW() WHERE url = ANY($1::text[])",
        urls,
    )
