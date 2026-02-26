from __future__ import annotations

import json
import re

import asyncpg

from http_client import Fetcher
from logger import log
from parsers.model_parser import parse_model_page
from pipeline import (
    enqueue_crawl_target,
    replace_model_specs,
    update_crawl_target_status,
    update_model_overview_fields,
    upsert_model,
)
from transformer import compute_spec_hash, normalize_spec


# Regex helpers for L / gal conversions
_L_RE = re.compile(r"([\d.]+)\s*[Ll](?:\b|$)")
_GAL_L_RE = re.compile(r"[\d.]+\s*gal\s*/\s*([\d.]+)\s*[Ll]", re.I)

# Sub-page URL suffixes and their crawl-target types
_SUBPAGE_SUFFIXES: list[tuple[str, str]] = [
    ("-engine",       "model_engine"),
    ("-transmission", "model_transmission"),
    ("-dimensions",   "model_dimensions"),
    ("-tests",        "model_tests"),
    ("-photos",       "model_photos"),
]


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
    tractor_type: str | None = meta.get("tractor_type")

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
        data["tractor_type"] = tractor_type

        # Extract structured fields from overview specs
        overview_fields = _extract_overview_fields(normalized_specs)

        content_hash = compute_spec_hash(normalized_specs)

        async with pool.acquire() as conn:
            model_id, specs_need_update = await upsert_model(
                conn,
                manufacturer_id,
                series_id,
                data,
            )

            # Persist overview-specific structured columns
            if overview_fields:
                await update_model_overview_fields(conn, model_id, overview_fields)

            if specs_need_update:
                await replace_model_specs(
                    conn, model_id, normalized_specs, content_hash
                )

            # Enqueue all sub-page crawl targets
            base_url = url.removesuffix(".html")
            for suffix, target_type in _SUBPAGE_SUFFIXES:
                sub_url = f"{base_url}{suffix}.html"
                await enqueue_crawl_target(
                    conn,
                    url=sub_url,
                    target_type=target_type,
                    meta={"model_id": model_id, "tractor_type": tractor_type},
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


# ---------------------------------------------------------------------------
# Overview field extraction helpers
# ---------------------------------------------------------------------------


def _extract_overview_fields(specs: list[dict]) -> dict:
    """Extract structured columns from overview spec rows.

    Looks in the Mechanical, Engine, and PTO groups for values that
    belong on ``tractor_models`` columns rather than ``model_specifications``.
    """
    fields: dict = {}

    for spec in specs:
        group_lo = spec["group"].lower()
        key_lo = spec["key"].lower()
        value = spec.get("value") or ""

        if "mechanical" in group_lo:
            if "drive" in key_lo:
                fields["drive_type"] = value
            elif "steer" in key_lo:
                fields["steering_type"] = value
            elif "brake" in key_lo:
                fields["brake_type"] = value
            elif "cab" in key_lo:
                fields["cab_description"] = value

        elif "engine" in group_lo or "fuel" in key_lo:
            if "fuel tank" in key_lo or ("fuel" in key_lo and "tank" in key_lo):
                fields["fuel_tank_l"] = _parse_litres(value)
            elif "def" in key_lo and "tank" in key_lo:
                fields["def_tank_l"] = _parse_litres(value)

    return {k: v for k, v in fields.items() if v is not None}


def _parse_litres(text: str) -> float | None:
    """Extract the litre value from strings like '799.8 L' or '211.3 gal / 799.8 L'."""
    m = _GAL_L_RE.search(text)
    if m:
        return float(m.group(1))
    m2 = _L_RE.search(text)
    if m2:
        return float(m2.group(1))
    return None

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
    tractor_type: str | None = meta.get("tractor_type")

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
        data["tractor_type"] = tractor_type

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
