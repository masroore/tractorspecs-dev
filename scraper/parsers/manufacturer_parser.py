from __future__ import annotations

import re

from selectolax.parser import HTMLParser

# Brand page links follow this pattern on both listing pages:
# /farm-tractors/tractor-brands/{slug}/{slug}-tractors.html
_BRAND_HREF_RE = re.compile(r"/(farm|lawn)-tractors/tractor-brands/([^/]+)/")

_BASE_URL = "https://www.tractordata.com"


def parse_manufacturer_listing(html: HTMLParser) -> list[dict[str, str]]:
    """Parse a manufacturer listing page (/farm-tractors/index.html or
    /lawn-tractors/index.html).

    Returns a list of dicts with keys: name, slug, url, tractor_type.
    """
    results: list[dict[str, str]] = []
    seen_slugs: set[str] = set()

    for node in html.css("a[href]"):
        href: str = node.attributes.get("href", "").strip()
        m = _BRAND_HREF_RE.search(href)
        if not m:
            continue

        name: str = node.text(strip=True)
        if not name:
            continue

        tractor_type = m.group(1)  # 'farm' or 'lawn'
        slug = m.group(2)  # e.g. 'john-deere'

        if not slug or slug in seen_slugs:
            continue

        seen_slugs.add(slug)
        results.append(
            {
                "name": name,
                "slug": slug,
                "url": _make_absolute(href),
                "tractor_type": tractor_type,
            }
        )

    return results


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_absolute(href: str) -> str:
    if href.startswith("http"):
        return href
    if href.startswith("/"):
        return f"{_BASE_URL}{href}"
    return f"{_BASE_URL}/{href}"
