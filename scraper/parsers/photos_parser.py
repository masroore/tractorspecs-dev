"""Parse the photos sub-page (*-photos.html) from TractorData.com.

Photo URLs follow the pattern:
    /photos/F{nnn}/{id}/{id}-td4-b01-ext{angle}.jpg

This parser collects every ``<img>`` or ``<a>`` link that points to
the ``/photos/`` path prefix, and extracts any attribution text.

Returned list shape
-------------------
[
    {
        "image_url":   str,         # relative URL as on the site
        "attribution": str | None,
    },
    …
]
"""

from __future__ import annotations

import re

from selectolax.parser import HTMLParser


_PHOTO_URL_RE = re.compile(r"/photos/", re.I)
_ATTRIBUTION_RE = re.compile(r"(?:photos?\s+courtesy\s+of|credit[s]?:?)\s*(.+)", re.I)


def parse_photos_page(html: HTMLParser) -> list[dict]:
    """Return a list of photo dicts from the photos sub-page HTML."""
    attribution = _parse_attribution(html)
    image_urls = _collect_image_urls(html)

    return [{"image_url": url, "attribution": attribution} for url in image_urls]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _collect_image_urls(html: HTMLParser) -> list[str]:
    """Collect all unique photo URLs from img src and anchor href attributes."""
    seen: set[str] = set()
    urls: list[str] = []

    for node in html.css("img, a"):
        src = node.attributes.get("src") or node.attributes.get("href") or ""
        if _PHOTO_URL_RE.search(src) and src not in seen:
            seen.add(src)
            urls.append(src)

    return urls


def _parse_attribution(html: HTMLParser) -> str | None:
    """Find attribution text in the page body."""
    # Look in the spec table first
    for td in html.css("table.tdat td"):
        text = td.text(strip=True)
        m = _ATTRIBUTION_RE.search(text)
        if m:
            return m.group(1).strip()

    # Fall back to any paragraph or div text
    for node in html.css("p, div"):
        text = node.text(strip=True)
        m = _ATTRIBUTION_RE.search(text)
        if m:
            return m.group(1).strip()

    return None
