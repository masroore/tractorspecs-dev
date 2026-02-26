"""Export tractor data from the database to indented JSON files.

Each model is written to:
    {output_dir}/{manufacturer_slug}/{model_slug}.json

The JSON document contains the complete nested data model including
specifications, engine, tire options, tests, and photos.

Usage examples
--------------
# Export everything
python exporter.py

# Export one manufacturer
python exporter.py --manufacturer john-deere

# Export a single model
python exporter.py --model john-deere-6105m

# Dry-run (print paths without writing)
python exporter.py --limit 5 --dry-run
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import asyncpg

from config import settings
from db import close_db, init_db
from logger import log

# ---------------------------------------------------------------------------
# JSON serialisation helpers
# ---------------------------------------------------------------------------

_SCHEMA_VERSION = 1


def _default_serialiser(obj: Any) -> Any:
    """Convert non-JSON-native Python objects produced by asyncpg."""
    if isinstance(obj, Decimal):
        return float(obj)
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    raise TypeError(f"Object of type {type(obj).__name__!r} is not JSON serialisable")


def _row_to_dict(record: asyncpg.Record | None) -> dict[str, Any] | None:
    """Convert an asyncpg Record into a plain dict, skipping internal columns."""
    if record is None:
        return None
    _skip = {
        "id",
        "model_id",
        "manufacturer_id",
        "series_id",
        "created_at",
        "updated_at",
        "name_search",
        "content_hash",
        "is_active",
    }
    return {k: v for k, v in dict(record).items() if k not in _skip}


def _rows_to_list(records: list[asyncpg.Record]) -> list[dict[str, Any]]:
    return [_row_to_dict(r) for r in records]


# ---------------------------------------------------------------------------
# Database queries
# ---------------------------------------------------------------------------


async def _fetch_model_ids(
    conn: asyncpg.Connection,
    manufacturer_slug: str | None,
    model_slug: str | None,
    limit: int | None,
) -> list[int]:
    """Return the list of model IDs to export according to the CLI filters."""
    clauses: list[str] = []
    params: list[Any] = []

    if manufacturer_slug:
        params.append(manufacturer_slug)
        clauses.append(f"mfr.slug = ${len(params)}")

    if model_slug:
        params.append(model_slug)
        clauses.append(f"tm.slug = ${len(params)}")

    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    limit_clause = f"LIMIT {limit}" if limit else ""

    rows = await conn.fetch(
        f"""
        SELECT tm.id
        FROM   tractor_models tm
        JOIN   manufacturers mfr ON mfr.id = tm.manufacturer_id
        {where}
        ORDER  BY mfr.slug, tm.slug
        {limit_clause}
        """,
        *params,
    )
    return [r["id"] for r in rows]


async def fetch_model_document(
    conn: asyncpg.Connection,
    model_id: int,
) -> dict[str, Any] | None:
    """Assemble the complete nested JSON document for a single model."""

    # Core row with manufacturer + series joined
    row = await conn.fetchrow(
        """
        SELECT
            tm.slug              AS model_slug,
            tm.name              AS model_name,
            tm.tractor_type,
            tm.production_start_year,
            tm.production_end_year,
            tm.horsepower_hp,
            tm.description,
            tm.drive_type,
            tm.steering_type,
            tm.brake_type,
            tm.cab_description,
            tm.fuel_tank_l,
            tm.def_tank_l,
            tm.seo_title,
            tm.seo_description,
            mfr.slug             AS mfr_slug,
            mfr.name             AS mfr_name,
            mfr.country          AS mfr_country,
            mfr.description      AS mfr_description,
            mfr.founded_year     AS mfr_founded_year,
            mfr.logo_path        AS mfr_logo_path,
            s.slug               AS series_slug,
            s.name               AS series_name,
            s.tractor_type       AS series_tractor_type,
            s.production_start_year AS series_start_year,
            s.production_end_year   AS series_end_year,
            cat.slug             AS category_slug,
            cat.name             AS category_name
        FROM  tractor_models tm
        JOIN  manufacturers mfr ON mfr.id = tm.manufacturer_id
        LEFT  JOIN series    s   ON s.id   = tm.series_id
        LEFT  JOIN categories cat ON cat.id = tm.category_id
        WHERE tm.id = $1
        """,
        model_id,
    )

    if row is None:
        return None

    # Build manufacturer sub-document
    manufacturer: dict[str, Any] = {
        "slug": row["mfr_slug"],
        "name": row["mfr_name"],
        "country": row["mfr_country"],
        "description": row["mfr_description"],
        "founded_year": row["mfr_founded_year"],
        "logo_path": row["mfr_logo_path"],
    }

    # Build series sub-document (nullable)
    series: dict[str, Any] | None = None
    if row["series_slug"]:
        series = {
            "slug": row["series_slug"],
            "name": row["series_name"],
            "tractor_type": row["series_tractor_type"],
            "production_start_year": row["series_start_year"],
            "production_end_year": row["series_end_year"],
        }

    # Build category sub-document (nullable)
    category: dict[str, Any] | None = None
    if row["category_slug"]:
        category = {
            "slug": row["category_slug"],
            "name": row["category_name"],
        }

    # Build model sub-document
    model: dict[str, Any] = {
        "slug": row["model_slug"],
        "name": row["model_name"],
        "tractor_type": row["tractor_type"],
        "production_start_year": row["production_start_year"],
        "production_end_year": row["production_end_year"],
        "horsepower_hp": row["horsepower_hp"],
        "description": row["description"],
        "drive_type": row["drive_type"],
        "steering_type": row["steering_type"],
        "brake_type": row["brake_type"],
        "cab_description": row["cab_description"],
        "fuel_tank_l": row["fuel_tank_l"],
        "def_tank_l": row["def_tank_l"],
        "seo_title": row["seo_title"],
        "seo_description": row["seo_description"],
    }

    # Specifications
    spec_rows = await conn.fetch(
        """
        SELECT spec_group, spec_key, spec_value, unit, display_order
        FROM   model_specifications
        WHERE  model_id = $1
        ORDER  BY display_order, id
        """,
        model_id,
    )
    specifications = _rows_to_list(spec_rows)

    # Engine (single row or null)
    engine_row = await conn.fetchrow(
        """
        SELECT
            engine_manufacturer, fuel_type, cylinders, cooling,
            displacement_ci, displacement_l,
            bore_in, bore_mm, stroke_in, stroke_mm,
            emissions_tier, emission_control,
            rated_power_hp, rated_power_kw, rated_rpm,
            torque_lbft, torque_nm, torque_rpm,
            starter_type, starter_volts, starter_hp,
            oil_change_hours, raw_data
        FROM model_engines
        WHERE model_id = $1
        """,
        model_id,
    )
    engine = dict(engine_row) if engine_row else None
    if engine and isinstance(engine.get("raw_data"), str):
        engine["raw_data"] = json.loads(engine["raw_data"])

    # Tire options
    tire_rows = await conn.fetch(
        """
        SELECT
            option_label, front_tire, rear_tire,
            wheelbase_in, wheelbase_cm,
            length_in, length_cm,
            width_in, width_cm,
            height_in, height_cm,
            weight_lbs, weight_kg,
            ground_clearance_in, ground_clearance_cm,
            front_tread_in, front_tread_cm,
            rear_tread_in, rear_tread_cm,
            display_order
        FROM  model_tire_options
        WHERE model_id = $1
        ORDER BY display_order
        """,
        model_id,
    )
    tire_options = _rows_to_list(tire_rows)

    # Tests
    test_rows = await conn.fetch(
        """
        SELECT
            test_name, test_date_start, test_date_end, test_url,
            pto_max_hp, pto_max_kw, pto_max_fuel_gph,
            pto_rated_eng_hp, pto_rated_eng_kw,
            pto_rated_pto_hp, pto_rated_pto_kw,
            drawbar_max_hp, drawbar_max_kw, drawbar_max_fuel_gph,
            drawbar_max_pull_lbs, drawbar_max_pull_kg,
            raw_data
        FROM  model_tests
        WHERE model_id = $1
        ORDER BY id
        """,
        model_id,
    )
    tests: list[dict[str, Any]] = []
    for t in test_rows:
        d = dict(t)
        if isinstance(d.get("raw_data"), str):
            d["raw_data"] = json.loads(d["raw_data"])
        tests.append(d)

    # Photos
    photo_rows = await conn.fetch(
        """
        SELECT image_url, attribution, display_order
        FROM   model_photos
        WHERE  model_id = $1
        ORDER  BY display_order
        """,
        model_id,
    )
    photos = _rows_to_list(photo_rows)

    return {
        "schema_version": _SCHEMA_VERSION,
        "exported_at": datetime.utcnow().isoformat() + "Z",
        "manufacturer": manufacturer,
        "series": series,
        "category": category,
        "model": model,
        "specifications": specifications,
        "engine": engine,
        "tire_options": tire_options,
        "tests": tests,
        "photos": photos,
    }


# ---------------------------------------------------------------------------
# Export logic
# ---------------------------------------------------------------------------


def write_model_json(
    document: dict[str, Any],
    output_dir: Path,
    *,
    skip_if_exists: bool = False,
) -> Path | None:
    """Serialise *document* to ``{output_dir}/{mfr_slug}/{model_slug}.json``.

    Returns the destination Path on success, or None when *skip_if_exists* is
    True and the file already exists.
    """
    mfr_slug = document["manufacturer"]["slug"]
    model_slug = document["model"]["slug"]
    dest_dir = output_dir / mfr_slug
    dest_path = dest_dir / f"{model_slug}.json"

    if skip_if_exists and dest_path.exists():
        return None

    dest_dir.mkdir(parents=True, exist_ok=True)
    dest_path.write_text(
        json.dumps(document, default=_default_serialiser, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return dest_path


async def export_models(
    pool: asyncpg.Pool,
    output_dir: Path,
    manufacturer_slug: str | None = None,
    model_slug: str | None = None,
    limit: int | None = None,
    dry_run: bool = False,
) -> int:
    """Export all matching models to JSON files. Returns count of models written."""
    async with pool.acquire() as conn:
        model_ids = await _fetch_model_ids(conn, manufacturer_slug, model_slug, limit)

    if not model_ids:
        log.info("exporter.no_models_found")
        return 0

    log.info("exporter.start", total=len(model_ids), dry_run=dry_run)

    written = 0
    for model_id in model_ids:
        async with pool.acquire() as conn:
            document = await fetch_model_document(conn, model_id)

        if document is None:
            log.warning("exporter.model_not_found", model_id=model_id)
            continue

        if dry_run:
            mfr_slug = document["manufacturer"]["slug"]
            model_slug_ = document["model"]["slug"]
            dest_path = output_dir / mfr_slug / f"{model_slug_}.json"
            log.info("exporter.model.dry_run", path=str(dest_path))
        else:
            path = write_model_json(document, output_dir)
            if path:
                log.info("exporter.model.written", path=str(path), model=document["model"]["slug"])

        written += 1

    log.info("exporter.done", written=written, dry_run=dry_run)
    return written


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export tractor models to JSON files")
    parser.add_argument(
        "--output-dir",
        default="/app/json-data",
        help="Root directory for JSON output (default: /app/json-data)",
    )
    parser.add_argument(
        "--manufacturer",
        metavar="SLUG",
        default=None,
        help="Export only models from this manufacturer slug",
    )
    parser.add_argument(
        "--model",
        metavar="SLUG",
        default=None,
        help="Export a single model by slug",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Maximum number of models to export",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Log what would be written without creating files",
    )
    return parser.parse_args()


async def main() -> None:
    args = _parse_args()
    output_dir = Path(args.output_dir)

    pool = await init_db(settings.database_url)
    try:
        await export_models(
            pool=pool,
            output_dir=output_dir,
            manufacturer_slug=args.manufacturer,
            model_slug=args.model,
            limit=args.limit,
            dry_run=args.dry_run,
        )
    finally:
        await close_db(pool)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        log.info("exporter.interrupted")
        sys.exit(0)
