from __future__ import annotations

import re

from selectolax.parser import HTMLParser

# Model page URLs are sharded by numeric segments:
# /farm-tractors/011/7/3/11738-john-deere-6m-105.html
_MODEL_HREF_RE = re.compile(r"/(farm|lawn)-tractors/\d+/\d+/\d+/[^/]+\.html$")

_BASE_URL = "https://www.tractordata.com"


def parse_manufacturer_page(html: HTMLParser) -> dict:
    """Parse a manufacturer overview page.

    Returns
    -------
    {
        "manufacturer": {
            "description": str | None,
            "country": str | None,
        },
        "series": [
            {
                "name": "All Models",
                "slug": "all-models",
                "production_start": None,
                "production_end": None,
                "models": [{"name": str, "url": str}, ...]
            }
        ]
    }

    TractorData brand pages contain a flat list of model links with numeric
    path sharding — there are no series groupings in the HTML.  All models
    are collected into a single synthetic series so the rest of the pipeline
    remains unchanged.
    """
    manufacturer_data = _parse_manufacturer_meta(html)
    models = _collect_model_links(html)

    series_list: list[dict] = []
    if models:
        series_list.append(
            {
                "name": "All Models",
                "slug": "all-models",
                "production_start": None,
                "production_end": None,
                "models": models,
            }
        )

    return {
        "manufacturer": manufacturer_data,
        "series": series_list,
    }


# ---------------------------------------------------------------------------
# Manufacturer meta
# ---------------------------------------------------------------------------


def _parse_manufacturer_meta(html: HTMLParser) -> dict[str, str | None]:
    description: str | None = None
    country: str | None = None

    # Description: first paragraph that is long enough to be meaningful
    for p in html.css("p"):
        text = p.text(strip=True)
        if len(text) > 60:
            description = text
            break

    return {"description": description, "country": country}


# ---------------------------------------------------------------------------
# Model link collection
# ---------------------------------------------------------------------------


def _collect_model_links(html: HTMLParser) -> list[dict[str, str]]:
    models: list[dict[str, str]] = []
    seen_urls: set[str] = set()

    for anchor in html.css("a[href]"):
        href: str = anchor.attributes.get("href", "").strip()
        if not _MODEL_HREF_RE.search(href):
            continue

        name: str = anchor.text(strip=True)
        if not name:
            continue

        url = _make_absolute(href)
        if url in seen_urls:
            continue

        seen_urls.add(url)
        models.append({"name": name, "url": url})

    return models


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_absolute(href: str) -> str:
    if href.startswith("http"):
        return href
    if href.startswith("/"):
        return f"{_BASE_URL}{href}"
    return f"{_BASE_URL}/{href}"
