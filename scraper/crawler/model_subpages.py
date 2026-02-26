"""Dispatcher for all model sub-page crawl targets.

Handles five target types:
    - model_engine
    - model_transmission
    - model_dimensions
    - model_tests
    - model_photos

Each crawler function fetches the sub-page HTML and delegates to the
appropriate parser + pipeline pair.
"""

from __future__ import annotations

import json
from pathlib import Path

import asyncpg

from config import settings
from exporter import fetch_model_document, write_model_json
from http_client import Fetcher
from logger import log
from parsers.dimensions_parser import parse_dimensions_page
from parsers.engine_parser import parse_engine_page
from parsers.photos_parser import parse_photos_page
from parsers.tests_parser import parse_tests_page
from parsers.transmission_parser import parse_transmission_page
from pipeline import (
    is_model_fully_scraped,
    replace_model_photos,
    replace_model_tire_options,
    update_crawl_target_status,
    upsert_model_engine,
    upsert_model_test,
    upsert_model_transmission,
)


# ---------------------------------------------------------------------------
# Generic sub-page crawl helper
# ---------------------------------------------------------------------------


async def crawl_model_subpage(
    fetcher: Fetcher,
    pool: asyncpg.Pool,
    target: asyncpg.Record,
) -> None:
    """Dispatch a sub-page crawl target to the appropriate handler."""
    url: str = target["url"]
    target_type: str = target["type"]
    meta: dict = json.loads(target["meta"] or "{}")
    model_id: int | None = meta.get("model_id")

    if not model_id:
        log.error("crawler.subpage.no_model_id", url=url, type=target_type)
        async with pool.acquire() as conn:
            await update_crawl_target_status(
                conn, url, "failed", error="Missing model_id in meta"
            )
        return

    log.info("crawler.subpage.start", url=url, type=target_type, model_id=model_id)

    _handlers = {
        "model_engine": _handle_engine,
        "model_transmission": _handle_transmission,
        "model_dimensions": _handle_dimensions,
        "model_tests": _handle_tests,
        "model_photos": _handle_photos,
    }

    handler = _handlers.get(target_type)
    if not handler:
        log.error("crawler.subpage.unknown_type", type=target_type, url=url)
        async with pool.acquire() as conn:
            await update_crawl_target_status(
                conn, url, "failed", error=f"Unknown target type: {target_type}"
            )
        return

    try:
        html = await fetcher.fetch(url)

        async with pool.acquire() as conn:
            await handler(conn, model_id, html)
            await update_crawl_target_status(conn, url, "done")

            if await is_model_fully_scraped(conn, model_id):
                document = await fetch_model_document(conn, model_id)
                if document is not None:
                    output_dir = Path(settings.json_export_dir)
                    path = write_model_json(document, output_dir, skip_if_exists=True)
                    if path:
                        log.info(
                            "crawler.subpage.json_exported",
                            model_id=model_id,
                            path=str(path),
                        )
                    else:
                        log.debug(
                            "crawler.subpage.json_already_exists",
                            model_id=model_id,
                        )

        log.info("crawler.subpage.done", url=url, type=target_type, model_id=model_id)

    except Exception as exc:
        log.error("crawler.subpage.error", url=url, type=target_type, error=str(exc))
        async with pool.acquire() as conn:
            await update_crawl_target_status(conn, url, "failed", error=str(exc))
        raise


# ---------------------------------------------------------------------------
# Per-type handlers
# ---------------------------------------------------------------------------


async def _handle_engine(
    conn: asyncpg.Connection,
    model_id: int,
    html,
) -> None:
    data = parse_engine_page(html)
    await upsert_model_engine(conn, model_id, data)
    log.debug("crawler.subpage.engine_upserted", model_id=model_id)


async def _handle_transmission(
    conn: asyncpg.Connection,
    model_id: int,
    html,
) -> None:
    data = parse_transmission_page(html)
    await upsert_model_transmission(conn, model_id, data)
    log.debug("crawler.subpage.transmission_upserted", model_id=model_id)


async def _handle_dimensions(
    conn: asyncpg.Connection,
    model_id: int,
    html,
) -> None:
    data = parse_dimensions_page(html)
    tire_options = data.get("tire_options", [])
    dimensions = data.get("dimensions", {})
    await replace_model_tire_options(conn, model_id, tire_options, dimensions)
    log.debug(
        "crawler.subpage.tire_options_replaced",
        model_id=model_id,
        count=len(tire_options),
    )


async def _handle_tests(
    conn: asyncpg.Connection,
    model_id: int,
    html,
) -> None:
    tests = parse_tests_page(html)
    for test in tests:
        await upsert_model_test(conn, model_id, test)
    log.debug("crawler.subpage.tests_upserted", model_id=model_id, count=len(tests))


async def _handle_photos(
    conn: asyncpg.Connection,
    model_id: int,
    html,
) -> None:
    photos = parse_photos_page(html)
    await replace_model_photos(conn, model_id, photos)
    log.debug(
        "crawler.subpage.photos_replaced",
        model_id=model_id,
        count=len(photos),
    )
