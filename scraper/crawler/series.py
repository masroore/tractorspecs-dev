from __future__ import annotations

import json

import asyncpg

from http_client import Fetcher
from logger import log
from parsers.series_parser import parse_manufacturer_page
from pipeline import (
    enqueue_crawl_target,
    update_crawl_target_status,
    upsert_manufacturer,
    upsert_series,
)


async def crawl_manufacturer_page(
    fetcher: Fetcher,
    pool: asyncpg.Pool,
    target: asyncpg.Record,
) -> None:
    """Crawl a single manufacturer page and enqueue model URLs.

    *target* is a row from crawl_targets (type='manufacturer').
    meta contains {"manufacturer_id": int, "slug": str}.
    """
    url: str = target["url"]
    meta: dict = json.loads(target["meta"] or "{}")
    manufacturer_id: int = meta.get("manufacturer_id")
    tractor_type: str | None = meta.get("tractor_type")

    if not manufacturer_id:
        log.error("crawler.series.no_manufacturer_id", url=url, meta=meta)
        async with pool.acquire() as conn:
            await update_crawl_target_status(
                conn, url, "failed", error="Missing manufacturer_id in meta"
            )
        return

    log.info("crawler.series.start", url=url, manufacturer_id=manufacturer_id)

    try:
        html = await fetcher.fetch(url)
        result = parse_manufacturer_page(html)

        async with pool.acquire() as conn:
            # Update manufacturer with any newly-scraped description/country
            mfr_meta = result["manufacturer"]
            if mfr_meta.get("description") or mfr_meta.get("country"):
                await conn.execute(
                    """
                    UPDATE manufacturers
                    SET description = COALESCE($1, description),
                        country     = COALESCE($2, country),
                        updated_at  = NOW()
                    WHERE id = $3
                    """,
                    mfr_meta.get("description"),
                    mfr_meta.get("country"),
                    manufacturer_id,
                )

            # Upsert each series and enqueue model URLs
            total_models_enqueued = 0
            for series_data in result["series"]:
                # Propagate tractor_type into the series row
                series_data["tractor_type"] = tractor_type
                series_id = await upsert_series(conn, manufacturer_id, series_data)

                for model_link in series_data.get("models", []):
                    await enqueue_crawl_target(
                        conn,
                        url=model_link["url"],
                        target_type="model",
                        meta={
                            "manufacturer_id": manufacturer_id,
                            "series_id": series_id,
                            "name": model_link.get("name"),
                            "tractor_type": tractor_type,
                        },
                        parent_id=target["id"],
                    )
                    total_models_enqueued += 1

            await update_crawl_target_status(conn, url, "done")

        log.info(
            "crawler.series.done",
            url=url,
            series=len(result["series"]),
            models_enqueued=total_models_enqueued,
        )

    except Exception as exc:
        log.error("crawler.series.error", url=url, error=str(exc))
        async with pool.acquire() as conn:
            await update_crawl_target_status(conn, url, "failed", error=str(exc))
        raise
