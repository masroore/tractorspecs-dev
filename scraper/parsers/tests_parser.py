"""Parse the tests sub-page (*-tests.html) from TractorData.com.

A single page may contain multiple test blocks separated by group headers.
Each block contains:
  - Test name (from the group header, e.g. "OCED Tractor Test 3100")
  - Date range (e.g. "July-August 2017")
  - External test URL
  - PTO measurements (max power/fuel, rated engine-speed, rated PTO-speed)
  - Drawbar measurements (max power/fuel, max pull)

Returned dict shape
-------------------
[
    {
        "test_name":            str | None,
        "test_date_start":      str | None,   # ISO date or raw string
        "test_date_end":        str | None,
        "test_url":             str | None,
        "pto_max_hp":           float | None,
        "pto_max_kw":           float | None,
        "pto_max_fuel_gph":     float | None,
        "pto_rated_eng_hp":     float | None,
        "pto_rated_eng_kw":     float | None,
        "pto_rated_pto_hp":     float | None,
        "pto_rated_pto_kw":     float | None,
        "drawbar_max_hp":       float | None,
        "drawbar_max_kw":       float | None,
        "drawbar_max_fuel_gph": float | None,
        "drawbar_max_pull_lbs": float | None,
        "drawbar_max_pull_kg":  float | None,
        "raw_data":             dict,
    },
    …
]
"""
from __future__ import annotations

import re

from selectolax.parser import HTMLParser

# ---------------------------------------------------------------------------
# Regex helpers
# ---------------------------------------------------------------------------

_FLOAT_RE = re.compile(r"[\d,]+\.?\d*")
_HP_KW_RE = re.compile(r"([\d.]+)\s*hp\s*/\s*([\d.]+)\s*kw", re.I)
_HP_ONLY_RE = re.compile(r"([\d.]+)\s*hp", re.I)
_KW_ONLY_RE = re.compile(r"([\d.]+)\s*kw", re.I)
_GPH_RE = re.compile(r"([\d.]+)\s*gal(?:lon)?s?/hr?", re.I)
_LBS_KG_RE = re.compile(r"([\d,]+(?:\.\d+)?)\s*lbs?\s*/\s*([\d,]+(?:\.\d+)?)\s*kg", re.I)
_LBS_ONLY_RE = re.compile(r"([\d,]+(?:\.\d+)?)\s*lbs?", re.I)

# Month names used to detect date rows
_MONTH_RE = re.compile(
    r"(January|February|March|April|May|June|July|August|September|October|November|December)",
    re.I,
)
_YEAR_RE = re.compile(r"\b((?:19|20)\d{2})\b")


def _first_float(text: str) -> float | None:
    m = _FLOAT_RE.search(text.replace(",", ""))
    return float(m.group()) if m else None


def _hp_kw(text: str) -> tuple[float | None, float | None]:
    m = _HP_KW_RE.search(text)
    if m:
        return float(m.group(1)), float(m.group(2))
    hp = _HP_ONLY_RE.search(text)
    kw = _KW_ONLY_RE.search(text)
    return (float(hp.group(1)) if hp else None), (float(kw.group(1)) if kw else None)


def _lbs_kg(text: str) -> tuple[float | None, float | None]:
    m = _LBS_KG_RE.search(text)
    if m:
        return float(m.group(1).replace(",", "")), float(m.group(2).replace(",", ""))
    ml = _LBS_ONLY_RE.search(text)
    return (float(ml.group(1).replace(",", "")) if ml else None), None


# ---------------------------------------------------------------------------
# Main parser
# ---------------------------------------------------------------------------


def parse_tests_page(html: HTMLParser) -> list[dict]:
    """Return a list of test result dicts from the tests sub-page HTML."""
    # Collect raw row data grouped by test block
    test_blocks = _split_into_blocks(html)
    return [_parse_block(block) for block in test_blocks]


# ---------------------------------------------------------------------------
# Block splitter
# ---------------------------------------------------------------------------


def _split_into_blocks(html: HTMLParser) -> list[list[tuple[str, str]]]:
    """Split table rows into per-test blocks.

    Group-header rows (colspan=2 cells containing a test name) indicate
    the start of a new block.
    """
    blocks: list[list[tuple[str, str]]] = []
    current: list[tuple[str, str]] = []

    for tr in html.css("table.tdat tr"):
        cells = tr.css("td")
        if not cells:
            continue

        # Group-header row
        if cells[0].attributes.get("colspan"):
            header_text = cells[0].text(strip=True)
            if header_text and _looks_like_test_name(header_text):
                if current:
                    blocks.append(current)
                current = [("__test_name__", header_text)]
            elif current:
                # Sub-section header (PTO, Drawbar) — keep as a marker
                current.append(("__section__", header_text))
            else:
                current = [("__section__", header_text)]
            continue

        if len(cells) < 2:
            continue

        key = cells[0].text(strip=True)
        value = cells[-1].text(strip=True)

        # Capture external link text / URL
        a = cells[-1].css_first("a")
        if a:
            href = a.attributes.get("href", "")
            if href and not value:
                value = href
            elif href:
                current.append(("__test_url__", href))

        if key or value:
            current.append((key, value))

    if current:
        blocks.append(current)

    return blocks if blocks else [current]


def _looks_like_test_name(text: str) -> bool:
    """Heuristic: a test-name header usually contains 'test' or a year."""
    lo = text.lower()
    return "test" in lo or bool(_YEAR_RE.search(text))


# ---------------------------------------------------------------------------
# Block parser
# ---------------------------------------------------------------------------


def _parse_block(rows: list[tuple[str, str]]) -> dict:
    test: dict = {
        "test_name": None,
        "test_date_start": None,
        "test_date_end": None,
        "test_url": None,
        "pto_max_hp": None,
        "pto_max_kw": None,
        "pto_max_fuel_gph": None,
        "pto_rated_eng_hp": None,
        "pto_rated_eng_kw": None,
        "pto_rated_pto_hp": None,
        "pto_rated_pto_kw": None,
        "drawbar_max_hp": None,
        "drawbar_max_kw": None,
        "drawbar_max_fuel_gph": None,
        "drawbar_max_pull_lbs": None,
        "drawbar_max_pull_kg": None,
        "raw_data": {},
    }
    raw: dict[str, str] = {}

    current_section = "header"

    for key, value in rows:
        if key == "__test_name__":
            test["test_name"] = value
            continue

        if key == "__test_url__":
            test["test_url"] = value
            continue

        if key == "__section__":
            lo = value.lower()
            if "pto" in lo:
                current_section = "pto"
            elif "drawbar" in lo:
                current_section = "drawbar"
            continue

        key_lo = key.lower()

        # Date row — e.g. "Test dates: July-August 2017"
        if _MONTH_RE.search(value):
            months = _MONTH_RE.findall(value)
            year_m = _YEAR_RE.search(value)
            year = year_m.group() if year_m else ""
            if months:
                test["test_date_start"] = f"{months[0]} {year}".strip()
                test["test_date_end"] = f"{months[-1]} {year}".strip()
            continue

        # URL / file row
        if "file" in key_lo or "report" in key_lo or "download" in key_lo:
            if not test["test_url"]:
                test["test_url"] = value
            continue

        if current_section == "pto":
            _parse_pto_row(test, key_lo, value)
        elif current_section == "drawbar":
            _parse_drawbar_row(test, key_lo, value)
        else:
            raw[key] = value

    test["raw_data"] = raw
    return test


def _parse_pto_row(test: dict, key_lo: str, value: str) -> None:
    gph_m = _GPH_RE.search(value)
    gph = float(gph_m.group(1)) if gph_m else None
    hp, kw = _hp_kw(value)

    if "max" in key_lo:
        test["pto_max_hp"] = hp
        test["pto_max_kw"] = kw
        if gph:
            test["pto_max_fuel_gph"] = gph
    elif "engine" in key_lo or "eng" in key_lo:
        test["pto_rated_eng_hp"] = hp
        test["pto_rated_eng_kw"] = kw
    elif "pto" in key_lo or "power take" in key_lo:
        test["pto_rated_pto_hp"] = hp
        test["pto_rated_pto_kw"] = kw
    elif hp:
        # First un-labelled hp reading → treat as max
        if not test["pto_max_hp"]:
            test["pto_max_hp"] = hp
            test["pto_max_kw"] = kw


def _parse_drawbar_row(test: dict, key_lo: str, value: str) -> None:
    gph_m = _GPH_RE.search(value)
    gph = float(gph_m.group(1)) if gph_m else None
    hp, kw = _hp_kw(value)

    if "max" in key_lo and "pull" in key_lo:
        lbs, kg = _lbs_kg(value)
        test["drawbar_max_pull_lbs"] = lbs
        test["drawbar_max_pull_kg"] = kg
    elif "max" in key_lo:
        test["drawbar_max_hp"] = hp
        test["drawbar_max_kw"] = kw
        if gph:
            test["drawbar_max_fuel_gph"] = gph
    elif hp and not test["drawbar_max_hp"]:
        test["drawbar_max_hp"] = hp
        test["drawbar_max_kw"] = kw
