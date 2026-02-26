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
    specs = _parse_specs(html)
    start_year, end_year = _extract_years_from_specs(specs)
    description = _parse_description(html)
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
    # TractorData puts the model name in an H1 or a span with class tdMt
    for selector in ("h1", ".tdMt", "h2"):
        node = html.css_first(selector)
        if node:
            text = node.text(strip=True)
            if text:
                return text

    # Fallback: page <title> — strip trailing " - TractorData.com" etc.
    title = html.css_first("title")
    if title:
        raw = title.text(strip=True)
        return re.split(r"\s*[-|]\s*", raw)[0].strip()

    return "Unknown"


# ---------------------------------------------------------------------------
# Production years
# ---------------------------------------------------------------------------

_YEAR_RANGE_RE = re.compile(r"(\d{4})[–\-](\d{4})")
_YEAR_SINGLE_RE = re.compile(r"\b((?:19|20)\d{2})\b")


def _parse_years(html: HTMLParser) -> tuple[int | None, int | None]:
    """Derive production years from the parsed spec data."""
    # Spec parsing happens first; this is a fallback for callers that
    # want years without the full spec pass.  The primary path is
    # _extract_years_from_specs() called after _parse_specs().
    specs = _parse_specs(html)
    return _extract_years_from_specs(specs)


_YEAR_RE = re.compile(r"\b((?:19|20)\d{2})\b")


def _extract_years_from_specs(specs: list[dict]) -> tuple[int | None, int | None]:
    """Look for Introduced / Discontinued keys in the Production group."""
    start_year: int | None = None
    end_year: int | None = None

    for spec in specs:
        group_lower = spec["group"].lower()
        key_lower = spec["key"].lower()

        if "production" not in group_lower:
            continue

        m = _YEAR_RE.search(spec["value"])
        if not m:
            continue

        year = int(m.group(1))

        if "introduced" in key_lower or "built" in key_lower or "start" in key_lower:
            start_year = year
        elif "discontinued" in key_lower or "end" in key_lower or "last" in key_lower:
            end_year = year

    return start_year, end_year


# ---------------------------------------------------------------------------
# Description
# ---------------------------------------------------------------------------


def _parse_description(html: HTMLParser) -> str | None:
    for selector in (
        "div.tdArticleItemFull p",
        "div.tdArticleItem p",
        "article > p",
        "p",
    ):
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
    """Walk every <table class="tdat"> on the page.

    Within each table rows are either:
    - A group header:  <tr><td colspan="2">Group Name</td></tr>
    - A spec pair:     <tr><td>Key</td><td>Value</td></tr>
    """
    specs: list[dict] = []
    display_order = 0

    for table in html.css("table.tdat"):
        current_group = "General"

        for row in table.css("tr"):
            cells = row.css("td")

            if len(cells) == 1:
                # Group header row — has colspan="2"
                colspan = cells[0].attributes.get("colspan", "1")
                if str(colspan) == "2":
                    group_text = cells[0].text(strip=True)
                    if group_text:
                        current_group = group_text
                continue

            if len(cells) < 2:
                continue

            key = cells[0].text(strip=True)
            raw_value = cells[1].text(strip=True)

            if not key or not raw_value:
                continue

            normalized_value, unit = normalize_spec(key, raw_value)

            specs.append(
                {
                    "group": current_group,
                    "key": key,
                    "value": normalized_value,
                    "unit": unit,
                    "display_order": display_order,
                }
            )
            display_order += 1

    return specs


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
