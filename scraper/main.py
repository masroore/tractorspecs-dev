from __future__ import annotations

import asyncio
import argparse
import sys

from aiolimiter import AsyncLimiter

from config import settings
from crawler.manufacturers import crawl_manufacturers
from crawler.model_subpages import crawl_model_subpage
from crawler.models import crawl_model_page
from crawler.series import crawl_manufacturer_page
from db import close_db, init_db, run_migrations
from http_client import Fetcher
from logger import log
from pipeline import (
    fetch_pending_targets,
    mark_targets_in_progress,
    update_crawl_target_status,
)
from proxy_pool import ProxyPool
from storage import SnapshotStorage


# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="TractorSpecs scraper")
    parser.add_argument(
        "--type",
        choices=[
            "manufacturer",
            "model",
            "model_engine",
            "model_transmission",
            "model_dimensions",
            "model_tests",
            "model_photos",
        ],
        default=None,
        help="Limit processing to a single crawl target type.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Maximum number of targets to process (per type).",
    )
    parser.add_argument(
        "--retry-failed",
        action="store_true",
        help="Requeue all failed crawl targets before running.",
    )
    parser.add_argument(
        "--skip-seed",
        action="store_true",
        help="Skip the initial manufacturer listing crawl (useful when resuming).",
    )
    return parser.parse_args()


# ---------------------------------------------------------------------------
# Core processing loop
# ---------------------------------------------------------------------------


async def process_pending_targets(
    pool,
    fetcher: Fetcher,
    target_type: str,
    batch_size: int = 50,
    limit: int | None = None,
) -> int:
    """Process all pending crawl targets of *target_type*.

    Returns total number of targets processed.
    """
    crawl_fn = {
        "manufacturer": crawl_manufacturer_page,
        "model": crawl_model_page,
        "model_engine": crawl_model_subpage,
        "model_transmission": crawl_model_subpage,
        "model_dimensions": crawl_model_subpage,
        "model_tests": crawl_model_subpage,
        "model_photos": crawl_model_subpage,
    }[target_type]

    processed = 0

    while True:
        effective_batch = min(batch_size, limit - processed) if limit else batch_size

        async with pool.acquire() as conn:
            targets = await fetch_pending_targets(
                conn, target_type, batch_size=effective_batch
            )
            if not targets:
                break

            urls = [t["url"] for t in targets]
            await mark_targets_in_progress(conn, urls)

        log.info(
            "orchestrator.batch",
            type=target_type,
            batch_size=len(targets),
            processed_so_far=processed,
        )

        # Fan out — each crawl_fn manages its own DB connection and marks itself done/failed
        await asyncio.gather(
            *[crawl_fn(fetcher, pool, target) for target in targets],
            return_exceptions=True,
        )

        processed += len(targets)

        if limit and processed >= limit:
            log.info("orchestrator.limit_reached", limit=limit)
            break

    log.info("orchestrator.type_done", type=target_type, total=processed)
    return processed


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


async def main() -> None:
    args = _parse_args()

    log.info("scraper.start", type=args.type, limit=args.limit)

    # --- Database ---
    pool = await init_db(settings.database_url)
    await run_migrations(pool)

    # --- Requeue failed targets if requested ---
    if args.retry_failed:
        async with pool.acquire() as conn:
            result = await conn.execute(
                "UPDATE crawl_targets SET status='pending', updated_at=NOW() WHERE status='failed'"
            )
        log.info("scraper.retry_failed", result=result)

    # --- Proxy pool ---
    proxy_pool = ProxyPool(settings.webshare_api_key)
    await proxy_pool.load_proxies()

    # --- MinIO snapshot storage ---
    storage = SnapshotStorage(
        endpoint=settings.minio_endpoint,
        access_key=settings.minio_access_key,
        secret_key=settings.minio_secret_key,
        bucket=settings.minio_bucket,
    )
    await storage.ensure_bucket()

    # --- Rate limiter & concurrency semaphore ---
    limiter = AsyncLimiter(settings.rate_limit_rps, 1)
    semaphore = asyncio.Semaphore(settings.max_concurrency)

    # --- HTTP fetcher ---
    fetcher = Fetcher(
        proxy_pool=proxy_pool,
        limiter=limiter,
        semaphore=semaphore,
        storage=storage,
    )

    try:
        run_type = args.type  # None means run all phases

        # Phase 1: Seed crawl_targets from the manufacturer listing page
        if not args.skip_seed and run_type in (None, "manufacturer"):
            await crawl_manufacturers(fetcher, pool, settings.target_base_url)

        # Phase 2: Process manufacturer pages → discover series + enqueue models
        if run_type in (None, "manufacturer"):
            await process_pending_targets(
                pool,
                fetcher,
                "manufacturer",
                limit=args.limit,
            )

        # Phase 3: Process model pages → extract & store specs + enqueue sub-pages
        if run_type in (None, "model"):
            await process_pending_targets(
                pool,
                fetcher,
                "model",
                limit=args.limit,
            )

        # Phase 4: Process model sub-pages (engine, transmission, dimensions, tests, photos)
        _subpage_run_types = {
            "model_engine",
            "model_transmission",
            "model_dimensions",
            "model_tests",
            "model_photos",
        }
        for sub_type in sorted(_subpage_run_types):
            if run_type in (None, sub_type):
                await process_pending_targets(
                    pool,
                    fetcher,
                    sub_type,
                    limit=args.limit,
                )

    finally:
        await close_db(pool)
        log.info("scraper.finished")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        log.info("scraper.interrupted")
        sys.exit(0)
