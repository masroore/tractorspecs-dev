from __future__ import annotations

import asyncpg

from http_client import Fetcher
from logger import log
from parsers.manufacturer_parser import parse_manufacturer_listing
from pipeline import enqueue_crawl_target, upsert_manufacturer


async def crawl_manufacturers(
    fetcher: Fetcher,
    pool: asyncpg.Pool,
    base_url: str,
) -> None:
    """Fetch the manufacturer listing page and seed crawl_targets.

    1. Fetch the base URL (manufacturer listing page).
    2. Parse all manufacturer entries.
    3. Upsert each manufacturer into the DB.
    4. Enqueue each manufacturer URL as a 'manufacturer' crawl target.
    """
    listing_url = base_url.rstrip("/") + "/"
    log.info("crawler.manufacturers.start", url=listing_url)

    html = await fetcher.fetch(listing_url)
    manufacturers = parse_manufacturer_listing(html)

    log.info("crawler.manufacturers.found", count=len(manufacturers))

    async with pool.acquire() as conn:
        for mfr in manufacturers:
            manufacturer_id = await upsert_manufacturer(conn, mfr)

            await enqueue_crawl_target(
                conn,
                url=mfr["url"],
                target_type="manufacturer",
                meta={"manufacturer_id": manufacturer_id, "slug": mfr["slug"]},
            )

    log.info("crawler.manufacturers.done", enqueued=len(manufacturers))
