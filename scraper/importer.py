"""Import tractor data from JSON files into the database.

Reads every ``*.json`` file produced by ``exporter.py`` and calls the
existing idempotent pipeline upsert functions, so it is safe to run
repeatedly on the same directory tree.

Usage examples
--------------
# Import everything in the default volume directory
python importer.py

# Import from a custom directory
python importer.py --input-dir /tmp/backup

# Import a single file
python importer.py --file /app/json-data/john-deere/john-deere-6105m.json

# Validate JSON parsing without touching the database
python importer.py --dry-run --limit 5
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import Any

import asyncpg

from config import settings
from db import close_db, init_db
from logger import log
from pipeline import (
    enqueue_crawl_target,
    replace_model_photos,
    replace_model_specs,
    replace_model_tire_options,
    upsert_manufacturer,
    upsert_model,
    upsert_model_engine,
    upsert_model_test,
    upsert_model_transmission,
    upsert_series,
)
from transformer import compute_spec_hash


# ---------------------------------------------------------------------------
# File discovery
# ---------------------------------------------------------------------------


def _discover_files(input_dir: Path) -> list[Path]:
    """Return all ``*.json`` files under *input_dir*, sorted for determinism."""
    return sorted(input_dir.rglob("*.json"))


# ---------------------------------------------------------------------------
# Per-file import logic
# ---------------------------------------------------------------------------


async def _import_document(
    pool: asyncpg.Pool,
    document: dict[str, Any],
) -> str:
    """Persist a single tractor JSON document to the database.

    Returns the model slug for logging purposes.
    """
    mfr_data = document["manufacturer"]
    series_data = document.get("series")
    model_data = document["model"]
    specs = document.get("specifications") or []
    engine = document.get("engine")
    tire_options = document.get("tire_options") or []
    tests = document.get("tests") or []
    photos = document.get("photos") or []

    async with pool.acquire() as conn:
        # 1. Manufacturer
        manufacturer_id = await upsert_manufacturer(conn, mfr_data)

        # 2. Series (optional)
        series_id: int | None = None
        if series_data:
            series_id = await upsert_series(conn, manufacturer_id, series_data)

        # 3. Model
        model_id, specs_need_update = await upsert_model(
            conn, manufacturer_id, series_id, model_data
        )

        # 4. Specifications
        if specs and specs_need_update:
            content_hash = compute_spec_hash(specs)
            await replace_model_specs(conn, model_id, specs, content_hash)

        # 5. Engine
        if engine:
            await upsert_model_engine(conn, model_id, engine)

        # 6. Tire options & dimensions
        if tire_options:
            # Dimensions are stored inline on the first tire option row
            first = tire_options[0] if tire_options else {}
            _dim_keys = {
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
            }
            dimensions = {
                k: first.get(k) for k in _dim_keys if first.get(k) is not None
            }
            await replace_model_tire_options(conn, model_id, tire_options, dimensions)

        # 7. Tests
        for test in tests:
            await upsert_model_test(conn, model_id, test)

        # 8. Photos
        if photos:
            await replace_model_photos(conn, model_id, photos)

    return model_data.get("slug", "<unknown>")


# ---------------------------------------------------------------------------
# Batch import
# ---------------------------------------------------------------------------


async def import_files(
    pool: asyncpg.Pool,
    files: list[Path],
    dry_run: bool = False,
) -> tuple[int, int]:
    """Import a list of JSON files. Returns (succeeded, failed) counts."""
    succeeded = 0
    failed = 0

    for path in files:
        log.info("importer.file.start", path=str(path))
        try:
            raw = path.read_text(encoding="utf-8")
            document = json.loads(raw)

            schema_version = document.get("schema_version")
            if schema_version != 1:
                log.warning(
                    "importer.file.unknown_schema_version",
                    path=str(path),
                    version=schema_version,
                )

            if dry_run:
                model_slug = document.get("model", {}).get("slug", "<unknown>")
                log.info("importer.file.dry_run", path=str(path), model=model_slug)
            else:
                model_slug = await _import_document(pool, document)
                log.info("importer.file.done", path=str(path), model=model_slug)

            succeeded += 1

        except Exception as exc:
            log.error("importer.file.error", path=str(path), error=str(exc))
            failed += 1

    log.info("importer.done", succeeded=succeeded, failed=failed)
    return succeeded, failed


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Import tractor models from JSON files"
    )
    parser.add_argument(
        "--input-dir",
        default="/app/json-data",
        help="Root directory to scan for JSON files (default: /app/json-data)",
    )
    parser.add_argument(
        "--file",
        metavar="PATH",
        default=None,
        help="Import a single JSON file instead of scanning a directory",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Maximum number of files to process",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Parse and validate JSON without writing to the database",
    )
    return parser.parse_args()


async def main() -> None:
    args = _parse_args()

    if args.file:
        files: list[Path] = [Path(args.file)]
    else:
        input_dir = Path(args.input_dir)
        if not input_dir.exists():
            log.error("importer.input_dir_not_found", path=str(input_dir))
            sys.exit(1)
        files = _discover_files(input_dir)

    if args.limit:
        files = files[: args.limit]

    log.info("importer.start", files=len(files), dry_run=args.dry_run)

    pool = await init_db(settings.database_url)
    try:
        succeeded, failed = await import_files(pool, files, dry_run=args.dry_run)
        if failed:
            sys.exit(1)
    finally:
        await close_db(pool)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        log.info("importer.interrupted")
        sys.exit(0)
