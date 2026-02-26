from __future__ import annotations

from selectolax.parser import HTMLParser

from transformer import build_slug


def parse_manufacturer_listing(html: HTMLParser) -> list[dict[str, str]]:
    """Parse the manufacturer listing page.

    Returns a list of dicts with keys: name, slug, url.

    TractorData's manufacturer listing page renders each manufacturer as a
    table cell containing an anchor tag.  The selectors below target that
    structure; adjust if the site markup changes.
    """
    results: list[dict[str, str]] = []
    seen_slugs: set[str] = set()

    # Primary selector: links inside the manufacturer grid
    candidates = html.css("table.mfr-links a") or html.css("div.mfr-list a")

    # Fallback: any link whose href starts with /tractors/
    if not candidates:
        candidates = [
            node
            for node in html.css("a[href]")
            if node.attributes.get("href", "").startswith("/tractors/")
        ]

    for node in candidates:
        href: str = node.attributes.get("href", "").strip()
        name: str = node.text(strip=True)

        if not href or not name:
            continue

        # Derive absolute URL (href may be relative)
        url = _make_absolute(href)

        # Derive slug from URL path or from name as fallback
        slug = _slug_from_href(href) or build_slug(name)

        if not slug or slug in seen_slugs:
            continue

        seen_slugs.add(slug)
        results.append({"name": name, "slug": slug, "url": url})

    return results


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_BASE_URL = "https://www.tractordata.com"


def _make_absolute(href: str) -> str:
    if href.startswith("http"):
        return href
    if href.startswith("/"):
        return f"{_BASE_URL}{href}"
    return f"{_BASE_URL}/{href}"


def _slug_from_href(href: str) -> str:
    """Extract the manufacturer slug from a URL path like /tractors/john-deere/."""
    parts = [p for p in href.strip("/").split("/") if p]
    # Expect pattern: tractors/{manufacturer-slug}
    if len(parts) >= 2 and parts[0] == "tractors":
        return parts[1]
    return ""
