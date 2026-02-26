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


# ---------------------------------------------------------------------------
# Overview structured fields
# ---------------------------------------------------------------------------


async def update_model_overview_fields(
    conn: asyncpg.Connection,
    model_id: int,
    data: dict[str, Any],
) -> None:
    """Persist structured overview fields extracted from a model's overview page.

    These are columns on ``tractor_models`` that are not spec rows:
    drive_type, steering_type, brake_type, cab_description,
    fuel_tank_l, def_tank_l.
    Only non-None values from *data* are written; existing DB values are
    preserved when the incoming value is None.
    """
    await conn.execute(
        """
        UPDATE tractor_models
        SET drive_type      = COALESCE($2, drive_type),
            steering_type   = COALESCE($3, steering_type),
            brake_type      = COALESCE($4, brake_type),
            cab_description = COALESCE($5, cab_description),
            fuel_tank_l     = COALESCE($6, fuel_tank_l),
            def_tank_l      = COALESCE($7, def_tank_l),
            updated_at      = NOW()
        WHERE id = $1
        """,
        model_id,
        data.get("drive_type"),
        data.get("steering_type"),
        data.get("brake_type"),
        data.get("cab_description"),
        data.get("fuel_tank_l"),
        data.get("def_tank_l"),
    )

    log.debug("pipeline.model_overview_fields_updated", model_id=model_id)


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------


async def upsert_model_engine(
    conn: asyncpg.Connection,
    model_id: int,
    data: dict[str, Any],
) -> None:
    """Insert or update the model_engines row for *model_id*."""
    await conn.execute(
        """
        INSERT INTO model_engines (
            model_id, engine_manufacturer, fuel_type, cylinders, cooling,
            displacement_ci, displacement_l,
            bore_in, bore_mm, stroke_in, stroke_mm,
            emissions_tier, emission_control,
            rated_power_hp, rated_power_kw, rated_rpm,
            torque_lbft, torque_nm, torque_rpm,
            starter_type, starter_volts, starter_hp,
            oil_change_hours, raw_data,
            created_at, updated_at
        ) VALUES (
            $1, $2, $3, $4, $5,
            $6, $7,
            $8, $9, $10, $11,
            $12, $13,
            $14, $15, $16,
            $17, $18, $19,
            $20, $21, $22,
            $23, $24,
            NOW(), NOW()
        )
        ON CONFLICT (model_id) DO UPDATE
            SET engine_manufacturer = COALESCE(EXCLUDED.engine_manufacturer, model_engines.engine_manufacturer),
                fuel_type           = COALESCE(EXCLUDED.fuel_type,           model_engines.fuel_type),
                cylinders           = COALESCE(EXCLUDED.cylinders,           model_engines.cylinders),
                cooling             = COALESCE(EXCLUDED.cooling,             model_engines.cooling),
                displacement_ci     = COALESCE(EXCLUDED.displacement_ci,     model_engines.displacement_ci),
                displacement_l      = COALESCE(EXCLUDED.displacement_l,      model_engines.displacement_l),
                bore_in             = COALESCE(EXCLUDED.bore_in,             model_engines.bore_in),
                bore_mm             = COALESCE(EXCLUDED.bore_mm,             model_engines.bore_mm),
                stroke_in           = COALESCE(EXCLUDED.stroke_in,           model_engines.stroke_in),
                stroke_mm           = COALESCE(EXCLUDED.stroke_mm,           model_engines.stroke_mm),
                emissions_tier      = COALESCE(EXCLUDED.emissions_tier,      model_engines.emissions_tier),
                emission_control    = COALESCE(EXCLUDED.emission_control,    model_engines.emission_control),
                rated_power_hp      = COALESCE(EXCLUDED.rated_power_hp,      model_engines.rated_power_hp),
                rated_power_kw      = COALESCE(EXCLUDED.rated_power_kw,      model_engines.rated_power_kw),
                rated_rpm           = COALESCE(EXCLUDED.rated_rpm,           model_engines.rated_rpm),
                torque_lbft         = COALESCE(EXCLUDED.torque_lbft,         model_engines.torque_lbft),
                torque_nm           = COALESCE(EXCLUDED.torque_nm,           model_engines.torque_nm),
                torque_rpm          = COALESCE(EXCLUDED.torque_rpm,          model_engines.torque_rpm),
                starter_type        = COALESCE(EXCLUDED.starter_type,        model_engines.starter_type),
                starter_volts       = COALESCE(EXCLUDED.starter_volts,       model_engines.starter_volts),
                starter_hp          = COALESCE(EXCLUDED.starter_hp,          model_engines.starter_hp),
                oil_change_hours    = COALESCE(EXCLUDED.oil_change_hours,    model_engines.oil_change_hours),
                raw_data            = EXCLUDED.raw_data,
                updated_at          = NOW()
        """,
        model_id,
        data.get("engine_manufacturer"),
        data.get("fuel_type"),
        data.get("cylinders"),
        data.get("cooling"),
        data.get("displacement_ci"),
        data.get("displacement_l"),
        data.get("bore_in"),
        data.get("bore_mm"),
        data.get("stroke_in"),
        data.get("stroke_mm"),
        data.get("emissions_tier"),
        data.get("emission_control"),
        data.get("rated_power_hp"),
        data.get("rated_power_kw"),
        data.get("rated_rpm"),
        data.get("torque_lbft"),
        data.get("torque_nm"),
        data.get("torque_rpm"),
        data.get("starter_type"),
        data.get("starter_volts"),
        data.get("starter_hp"),
        data.get("oil_change_hours"),
        json.dumps(data.get("raw_data") or {}),
    )

    log.debug("pipeline.engine_upserted", model_id=model_id)


# ---------------------------------------------------------------------------
# Transmission
# ---------------------------------------------------------------------------


async def upsert_model_transmission(
    conn: asyncpg.Connection,
    model_id: int,
    data: dict[str, Any],
) -> None:
    """Persist transmission details as model_specifications rows.

    Stores under spec_group 'Transmission Detail' so they don't overwrite
    overview specs.  Existing rows in that group are replaced.
    """
    await conn.execute(
        "DELETE FROM model_specifications WHERE model_id=$1 AND spec_group='Transmission Detail'",
        model_id,
    )

    fields: list[tuple[str, str | None]] = [
        ("Transmission", data.get("transmission_name")),
        ("Gears", data.get("gear_type")),
        ("Speeds diagram", data.get("speeds_image_url")),
    ]

    records = [
        (model_id, "Transmission Detail", key, value, None, idx)
        for idx, (key, value) in enumerate(fields)
        if value is not None
    ]

    if records:
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

    log.debug("pipeline.transmission_upserted", model_id=model_id)


# ---------------------------------------------------------------------------
# Tire options & dimensions
# ---------------------------------------------------------------------------


async def replace_model_tire_options(
    conn: asyncpg.Connection,
    model_id: int,
    tire_options: list[dict[str, Any]],
    dimensions: dict[str, Any],
) -> None:
    """Replace all tire option rows for *model_id*.

    Dimension values (wheelbase, weight, etc.) are stored on the first
    (standard) tire option row.
    """
    await conn.execute(
        "DELETE FROM model_tire_options WHERE model_id = $1",
        model_id,
    )

    if not tire_options:
        return

    records = []
    for idx, opt in enumerate(tire_options):
        # Attach dimensions to the first (standard) row only
        dim = dimensions if idx == 0 else {}
        records.append(
            (
                model_id,
                opt.get("option_label") or "Standard",
                opt.get("front_tire"),
                opt.get("rear_tire"),
                dim.get("wheelbase_in"),
                dim.get("wheelbase_cm"),
                dim.get("length_in"),
                dim.get("length_cm"),
                dim.get("width_in"),
                dim.get("width_cm"),
                dim.get("height_in"),
                dim.get("height_cm"),
                dim.get("weight_lbs"),
                dim.get("weight_kg"),
                dim.get("ground_clearance_in"),
                dim.get("ground_clearance_cm"),
                dim.get("front_tread_in"),
                dim.get("front_tread_cm"),
                dim.get("rear_tread_in"),
                dim.get("rear_tread_cm"),
                idx,
            )
        )

    await conn.copy_records_to_table(
        "model_tire_options",
        records=records,
        columns=[
            "model_id",
            "option_label",
            "front_tire",
            "rear_tire",
            "wheelbase_in",
            "wheelbase_cm",
            "length_in",
            "length_cm",
            "width_in",
            "width_cm",
            "height_in",
            "height_cm",
            "weight_lbs",
            "weight_kg",
            "ground_clearance_in",
            "ground_clearance_cm",
            "front_tread_in",
            "front_tread_cm",
            "rear_tread_in",
            "rear_tread_cm",
            "display_order",
        ],
    )

    log.debug(
        "pipeline.tire_options_replaced",
        model_id=model_id,
        count=len(tire_options),
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


async def upsert_model_test(
    conn: asyncpg.Connection,
    model_id: int,
    data: dict[str, Any],
) -> None:
    """Insert a test result row.  Does not de-duplicate by name — multiple
    tests on the same page are all inserted."""
    await conn.execute(
        """
        INSERT INTO model_tests (
            model_id, test_name, test_date_start, test_date_end, test_url,
            pto_max_hp, pto_max_kw, pto_max_fuel_gph,
            pto_rated_eng_hp, pto_rated_eng_kw,
            pto_rated_pto_hp, pto_rated_pto_kw,
            drawbar_max_hp, drawbar_max_kw, drawbar_max_fuel_gph,
            drawbar_max_pull_lbs, drawbar_max_pull_kg,
            raw_data, created_at, updated_at
        ) VALUES (
            $1, $2, $3, $4, $5,
            $6, $7, $8,
            $9, $10,
            $11, $12,
            $13, $14, $15,
            $16, $17,
            $18, NOW(), NOW()
        )
        ON CONFLICT DO NOTHING
        """,
        model_id,
        data.get("test_name"),
        data.get("test_date_start"),
        data.get("test_date_end"),
        data.get("test_url"),
        data.get("pto_max_hp"),
        data.get("pto_max_kw"),
        data.get("pto_max_fuel_gph"),
        data.get("pto_rated_eng_hp"),
        data.get("pto_rated_eng_kw"),
        data.get("pto_rated_pto_hp"),
        data.get("pto_rated_pto_kw"),
        data.get("drawbar_max_hp"),
        data.get("drawbar_max_kw"),
        data.get("drawbar_max_fuel_gph"),
        data.get("drawbar_max_pull_lbs"),
        data.get("drawbar_max_pull_kg"),
        json.dumps(data.get("raw_data") or {}),
    )

    log.debug("pipeline.test_upserted", model_id=model_id, name=data.get("test_name"))


# ---------------------------------------------------------------------------
# Photos
# ---------------------------------------------------------------------------


async def replace_model_photos(
    conn: asyncpg.Connection,
    model_id: int,
    photos: list[dict[str, Any]],
) -> None:
    """Replace all photo rows for *model_id*."""
    await conn.execute(
        "DELETE FROM model_photos WHERE model_id = $1",
        model_id,
    )

    if not photos:
        return

    records = [
        (model_id, p["image_url"], p.get("attribution"), idx)
        for idx, p in enumerate(photos)
    ]

    await conn.copy_records_to_table(
        "model_photos",
        records=records,
        columns=["model_id", "image_url", "attribution", "display_order"],
    )

    log.debug("pipeline.photos_replaced", model_id=model_id, count=len(photos))


# ---------------------------------------------------------------------------
# Post-scrape completeness
# ---------------------------------------------------------------------------

_SUBPAGE_TARGET_TYPES: frozenset[str] = frozenset(
    {
        "model_engine",
        "model_transmission",
        "model_dimensions",
        "model_tests",
        "model_photos",
    }
)


async def is_model_fully_scraped(conn: asyncpg.Connection, model_id: int) -> bool:
    """Return True when all 5 sub-page crawl targets for *model_id* are done.

    Counts ``crawl_targets`` rows whose ``meta->>'model_id'`` matches
    *model_id* and whose ``type`` is one of the five sub-page types.
    All 5 must carry ``status='done'`` for this to return True.
    """
    row = await conn.fetchrow(
        """
        SELECT COUNT(*) AS done_count
        FROM   crawl_targets
        WHERE  (meta->>'model_id')::int = $1
          AND  type  = ANY($2::text[])
          AND  status = 'done'
        """,
        model_id,
        list(_SUBPAGE_TARGET_TYPES),
    )
    return int(row["done_count"]) == len(_SUBPAGE_TARGET_TYPES)
