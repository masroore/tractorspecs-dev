from __future__ import annotations

import asyncpg

from http_client import Fetcher
from logger import log
from parsers.manufacturer_parser import parse_manufacturer_listing
from pipeline import enqueue_crawl_target, upsert_manufacturer


# TractorData separates farm and lawn tractor brands into two listing pages.
_LISTING_PATHS = [
    "/farm-tractors/index.html",
    "/lawn-tractors/index.html",
]


async def crawl_manufacturers(
    fetcher: Fetcher,
    pool: asyncpg.Pool,
    base_url: str,
) -> None:
    """Fetch both manufacturer listing pages and seed crawl_targets.

    1. Fetch /farm-tractors/index.html and /lawn-tractors/index.html.
    2. Parse all manufacturer entries (deduplicated by slug).
    3. Upsert each manufacturer into the DB.
    4. Enqueue each brand-page URL as a 'manufacturer' crawl target,
       carrying tractor_type ('farm' or 'lawn') in meta.
    """
    base = base_url.rstrip("/")
    all_manufacturers: dict[str, dict[str, str]] = {}  # url → mfr dict

    for path in _LISTING_PATHS:
        listing_url = base + path
        log.info("crawler.manufacturers.fetch", url=listing_url)

        html = await fetcher.fetch(listing_url)
        manufacturers = parse_manufacturer_listing(html)

        log.info(
            "crawler.manufacturers.page_found",
            url=listing_url,
            count=len(manufacturers),
        )

        for mfr in manufacturers:
            url = mfr["url"]
            if url not in all_manufacturers:
                all_manufacturers[url] = mfr

    log.info("crawler.manufacturers.total", count=len(all_manufacturers))

    async with pool.acquire() as conn:
        for mfr in all_manufacturers.values():
            manufacturer_id = await upsert_manufacturer(conn, mfr)

            await enqueue_crawl_target(
                conn,
                url=mfr["url"],
                target_type="manufacturer",
                meta={
                    "manufacturer_id": manufacturer_id,
                    "slug": mfr["slug"],
                    "tractor_type": mfr["tractor_type"],
                },
            )

    log.info("crawler.manufacturers.done", enqueued=len(all_manufacturers))
