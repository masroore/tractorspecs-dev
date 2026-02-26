from __future__ import annotations

import re

from selectolax.parser import HTMLParser

from transformer import normalize_spec


def parse_model_page(html: HTMLParser) -> dict:
    """Parse a tractor model detail page.

    Returns
    -------
    {
        "name": str,
        "production_start_year": int | None,
        "production_end_year": int | None,
        "description": str | None,
        "horsepower_hp": float | None,
        "specs": [
            {"group": str, "key": str, "value": str, "unit": str | None}
        ]
    }
    """
    name = _parse_name(html)
    start_year, end_year = _parse_years(html)
    description = _parse_description(html)
    specs = _parse_specs(html)
    horsepower_hp = _extract_hp(specs)

    return {
        "name": name,
        "production_start_year": start_year,
        "production_end_year": end_year,
        "description": description,
        "horsepower_hp": horsepower_hp,
        "specs": specs,
    }


# ---------------------------------------------------------------------------
# Name
# ---------------------------------------------------------------------------


def _parse_name(html: HTMLParser) -> str:
    h1 = html.css_first("h1")
    if h1:
        return h1.text(strip=True)

    # Fallback: page title element
    title = html.css_first("title")
    if title:
        raw = title.text(strip=True)
        # Strip common suffixes like " - Specs & Data"
        return re.split(r"\s*[-|]\s*", raw)[0].strip()

    return "Unknown"


# ---------------------------------------------------------------------------
# Production years
# ---------------------------------------------------------------------------

_YEAR_RANGE_RE = re.compile(r"(\d{4})[–\-](\d{4})")
_YEAR_SINGLE_RE = re.compile(r"\b((?:19|20)\d{2})\b")


def _parse_years(html: HTMLParser) -> tuple[int | None, int | None]:
    # Look for year info in subtitle paragraphs, header spans, or breadcrumbs
    candidates = [
        html.css_first("p.model-years"),
        html.css_first("div.model-header span"),
        html.css_first("div.tractor-info"),
        html.css_first("h1"),
        html.css_first("h2"),
    ]

    for node in candidates:
        if node is None:
            continue
        text = node.text(strip=True)
        m = _YEAR_RANGE_RE.search(text)
        if m:
            return int(m.group(1)), int(m.group(2))
        m2 = _YEAR_SINGLE_RE.search(text)
        if m2:
            return int(m2.group(1)), None

    # Last resort: scan all visible text in the header area
    header = html.css_first("div#header, div.page-header, header")
    if header:
        text = header.text(strip=True)
        m = _YEAR_RANGE_RE.search(text)
        if m:
            return int(m.group(1)), int(m.group(2))

    return None, None


# ---------------------------------------------------------------------------
# Description
# ---------------------------------------------------------------------------


def _parse_description(html: HTMLParser) -> str | None:
    for selector in ("div.model-description p", "div.description p", "article > p"):
        node = html.css_first(selector)
        if node:
            text = node.text(strip=True)
            if len(text) > 40:
                return text
    return None


# ---------------------------------------------------------------------------
# Spec tables
# ---------------------------------------------------------------------------


def _parse_specs(html: HTMLParser) -> list[dict]:
    specs: list[dict] = []
    display_order = 0

    # TractorData renders specs in multiple <table> elements, each with a
    # <caption> or a preceding sibling heading that names the group.
    # We iterate every table and determine its group name.
    for table in html.css("table"):
        group = _get_group_name(table)
        if not group:
            continue

        for row in table.css("tr"):
            cells = row.css("td")
            if len(cells) < 2:
                continue

            key = cells[0].text(strip=True)
            raw_value = cells[1].text(strip=True)

            if not key or not raw_value:
                continue

            normalized_value, unit = normalize_spec(key, raw_value)

            specs.append(
                {
                    "group": group,
                    "key": key,
                    "value": normalized_value,
                    "unit": unit,
                    "display_order": display_order,
                }
            )
            display_order += 1

    return specs


def _get_group_name(table) -> str | None:  # type: ignore[return]
    """Determine the spec group name for a table."""
    # Option 1: <caption> element inside the table
    caption = table.css_first("caption")
    if caption:
        name = caption.text(strip=True)
        if name:
            return name

    # Option 2: Preceding <h2> or <h3> sibling (DOM walking)
    prev = table.prev
    while prev is not None:
        if hasattr(prev, "tag") and prev.tag in ("h2", "h3", "h4"):
            name = prev.text(strip=True)
            if name:
                return name
            break
        prev = getattr(prev, "prev", None)

    # Option 3: id or class attribute on the table
    table_id = table.attributes.get("id", "") or table.attributes.get("class", "")
    if table_id:
        return table_id.replace("-", " ").replace("_", " ").title()

    return None


# ---------------------------------------------------------------------------
# HP extraction
# ---------------------------------------------------------------------------

_HP_RE = re.compile(r"(\d+(?:\.\d+)?)")


def _extract_hp(specs: list[dict]) -> float | None:
    """Find the engine/PTO horsepower from the parsed spec list."""
    hp_keys = {
        "engine hp",
        "engine horsepower",
        "gross hp",
        "gross horsepower",
        "rated hp",
        "pto hp",
        "horsepower",
        "hp",
        "power",
        "max power",
        "max hp",
    }

    for spec in specs:
        if spec["key"].lower().strip() in hp_keys and spec.get("unit") == "hp":
            try:
                return float(spec["value"])
            except (ValueError, TypeError):
                pass

    # Fallback: first numeric hp-unit spec in the Engine group
    for spec in specs:
        if spec.get("unit") == "hp":
            try:
                return float(spec["value"])
            except (ValueError, TypeError):
                pass

    return None
