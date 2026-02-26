from __future__ import annotations

import json

import asyncpg

from http_client import Fetcher
from logger import log
from parsers.model_parser import parse_model_page
from pipeline import (
    replace_model_specs,
    update_crawl_target_status,
    upsert_model,
)
from transformer import compute_spec_hash, normalize_spec


async def crawl_model_page(
    fetcher: Fetcher,
    pool: asyncpg.Pool,
    target: asyncpg.Record,
) -> None:
    """Crawl a single tractor model page and persist its specifications.

    *target* is a row from crawl_targets (type='model').
    meta contains {"manufacturer_id": int, "series_id": int | null, "name": str | null}.
    """
    url: str = target["url"]
    meta: dict = json.loads(target["meta"] or "{}")
    manufacturer_id: int = meta.get("manufacturer_id")
    series_id: int | None = meta.get("series_id")

    if not manufacturer_id:
        log.error("crawler.model.no_manufacturer_id", url=url)
        async with pool.acquire() as conn:
            await update_crawl_target_status(
                conn, url, "failed", error="Missing manufacturer_id in meta"
            )
        return

    log.info("crawler.model.start", url=url)

    try:
        html = await fetcher.fetch(url)
        data = parse_model_page(html)

        # Normalize each raw spec value
        normalized_specs: list[dict] = []
        for idx, spec in enumerate(data.get("specs", [])):
            norm_value, unit = normalize_spec(spec["key"], spec["value"])
            normalized_specs.append(
                {
                    "group": spec["group"],
                    "key": spec["key"],
                    "value": norm_value,
                    "unit": unit or spec.get("unit"),
                    "display_order": spec.get("display_order", idx),
                }
            )

        data["specs"] = normalized_specs

        content_hash = compute_spec_hash(normalized_specs)

        async with pool.acquire() as conn:
            model_id, specs_need_update = await upsert_model(
                conn,
                manufacturer_id,
                series_id,
                data,
            )

            if specs_need_update:
                await replace_model_specs(
                    conn, model_id, normalized_specs, content_hash
                )

            await update_crawl_target_status(
                conn, url, "done", content_hash=content_hash
            )

        log.info(
            "crawler.model.done",
            url=url,
            model_id=model_id,
            specs=len(normalized_specs),
            updated=specs_need_update,
        )

    except Exception as exc:
        log.error("crawler.model.error", url=url, error=str(exc))
        async with pool.acquire() as conn:
            await update_crawl_target_status(conn, url, "failed", error=str(exc))
        raise
