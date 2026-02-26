from __future__ import annotations

import re

from selectolax.parser import HTMLParser, Node

from transformer import build_slug


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
                "name": str,
                "slug": str,
                "production_start": int | None,
                "production_end": int | None,
                "models": [
                    {"name": str, "url": str}
                ]
            }
        ]
    }
    """
    manufacturer_data = _parse_manufacturer_meta(html)
    series_list = _parse_series(html)

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

    # Description: first substantial paragraph near the top
    for p in html.css("div.mfr-description p, div#content p, article p"):
        text = p.text(strip=True)
        if len(text) > 60:
            description = text
            break

    # Country: look for a "country" labeled cell or span
    for node in html.css("td, li, span"):
        text = node.text(strip=True).lower()
        if "country" in text or "origin" in text:
            next_sib = node.next
            if next_sib:
                country = next_sib.text(strip=True) or None
            break

    return {"description": description, "country": country}


# ---------------------------------------------------------------------------
# Series & model listing
# ---------------------------------------------------------------------------

def _parse_series(html: HTMLParser) -> list[dict]:
    series_list: list[dict] = []
    current_series: dict | None = None

    # TractorData structures each series as an <h2> or <h3> followed by
    # a table or list of model links.
    for node in html.css("h2, h3, table.model-list, ul.model-list, div.series-block"):
        tag = node.tag.lower()

        if tag in ("h2", "h3"):
            # Flush previous series
            if current_series is not None:
                series_list.append(current_series)

            series_name = node.text(strip=True)
            if not series_name:
                current_series = None
                continue

            years = _extract_year_range(series_name)
            clean_name = re.sub(r"\s*\(?\d{4}[–\-]\d{4}\)?", "", series_name).strip()

            current_series = {
                "name": clean_name or series_name,
                "slug": build_slug(clean_name or series_name),
                "production_start": years[0],
                "production_end": years[1],
                "models": [],
            }

        elif tag in ("table", "ul", "div") and current_series is not None:
            # Collect all model links within this element
            for anchor in node.css("a[href]"):
                model_name = anchor.text(strip=True)
                href = anchor.attributes.get("href", "").strip()
                if not model_name or not href:
                    continue
                url = _make_absolute(href)
                current_series["models"].append({"name": model_name, "url": url})

    # Flush last series
    if current_series is not None:
        series_list.append(current_series)

    # Fallback: if no series structure found, gather all model links into a
    # synthetic "General" series
    if not series_list:
        models = _collect_all_model_links(html)
        if models:
            series_list.append({
                "name": "General",
                "slug": "general",
                "production_start": None,
                "production_end": None,
                "models": models,
            })

    return series_list


def _collect_all_model_links(html: HTMLParser) -> list[dict[str, str]]:
    models = []
    for anchor in html.css("a[href]"):
        href = anchor.attributes.get("href", "")
        # Links to model pages follow /tractors/{manufacturer}/{model}/ pattern
        parts = [p for p in href.strip("/").split("/") if p]
        if len(parts) == 3 and parts[0] == "tractors":
            name = anchor.text(strip=True)
            if name:
                models.append({"name": name, "url": _make_absolute(href)})
    return models


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_BASE_URL = "https://www.tractordata.com"
_YEAR_RANGE_RE = re.compile(r"(\d{4})[–\-](\d{4})")
_SINGLE_YEAR_RE = re.compile(r"\b(\d{4})\b")


def _extract_year_range(text: str) -> tuple[int | None, int | None]:
    m = _YEAR_RANGE_RE.search(text)
    if m:
        return int(m.group(1)), int(m.group(2))
    m2 = _SINGLE_YEAR_RE.search(text)
    if m2:
        return int(m2.group(1)), None
    return None, None


def _make_absolute(href: str) -> str:
    if href.startswith("http"):
        return href
    if href.startswith("/"):
        return f"{_BASE_URL}{href}"
    return f"{_BASE_URL}/{href}"
