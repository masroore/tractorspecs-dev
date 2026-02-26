"""Parse the dimensions sub-page (*-dimensions.html) from TractorData.com.

The page has two logical sections, both rendered as ``table.tdat``:

1. **Tires table** — one or more rows for standard + optional tire configs.
   Each row has front-tire and rear-tire values.
   Header row: model name spanning 2 cols, then "Front" / "Rear" labels.
   Data rows: label ("Standard", "Optional Ag" …), front value, rear value.

2. **Dimensions table** — standard key-value rows:
   Wheelbase, Length, Width, Height (cab), Weight, Ground clearance,
   Front tread, Rear tread.

Returned dict shape
-------------------
{
    "tire_options": [
        {
            "option_label":        str,           # "Standard", "Optional", …
            "front_tire":          str | None,
            "rear_tire":           str | None,
        },
        …
    ],
    "dimensions": {
        "wheelbase_in":         float | None,
        "wheelbase_cm":         float | None,
        "length_in":            float | None,
        "length_cm":            float | None,
        "width_in":             float | None,
        "width_cm":             float | None,
        "height_in":            float | None,
        "height_cm":            float | None,
        "weight_lbs":           float | None,
        "weight_kg":            float | None,
        "ground_clearance_in":  float | None,
        "ground_clearance_cm":  float | None,
        "front_tread_in":       float | None,
        "front_tread_cm":       float | None,
        "rear_tread_in":        float | None,
        "rear_tread_cm":        float | None,
    },
}
"""

from __future__ import annotations

import re

from selectolax.parser import HTMLParser


# ---------------------------------------------------------------------------
# Regex helpers
# ---------------------------------------------------------------------------

_FLOAT_RE = re.compile(r"[\d,]+\.?\d*")
_IN_CM_RE = re.compile(r"([\d.]+)\s*in\s*/\s*([\d.]+)\s*cm", re.I)
_LBS_KG_RE = re.compile(
    r"([\d,]+(?:\.\d+)?)\s*lbs?\s*/\s*([\d,]+(?:\.\d+)?)\s*kg", re.I
)


def _first_float(text: str) -> float | None:
    m = _FLOAT_RE.search(text.replace(",", ""))
    return float(m.group()) if m else None


def _in_cm(text: str) -> tuple[float | None, float | None]:
    m = _IN_CM_RE.search(text)
    if m:
        return float(m.group(1)), float(m.group(2))
    f = _first_float(text)
    return f, None


def _lbs_kg(text: str) -> tuple[float | None, float | None]:
    m = _LBS_KG_RE.search(text)
    if m:
        return float(m.group(1).replace(",", "")), float(m.group(2).replace(",", ""))
    f = _first_float(text)
    return f, None


# ---------------------------------------------------------------------------
# Main parser
# ---------------------------------------------------------------------------


def parse_dimensions_page(html: HTMLParser) -> dict:
    """Return tire options list and dimensions dict from the dimensions sub-page."""
    tire_options = _parse_tire_options(html)
    dimensions = _parse_dimensions(html)

    return {
        "tire_options": tire_options,
        "dimensions": dimensions,
    }


# ---------------------------------------------------------------------------
# Tire options
# ---------------------------------------------------------------------------


def _parse_tire_options(html: HTMLParser) -> list[dict]:
    """Extract the tire configuration table rows.

    The tires table is identified by having a header row that contains
    "Front" and "Rear" columns.
    """
    tire_options: list[dict] = []

    for table in html.css("table.tdat"):
        headers = [td.text(strip=True).lower() for td in table.css("tr:first-child td")]
        if "front" not in headers and "rear" not in headers:
            continue

        # Found the tires table
        for tr in table.css("tr"):
            cells = tr.css("td")
            texts = [c.text(strip=True) for c in cells]

            # Skip header rows and empty rows
            low = [t.lower() for t in texts]
            if not texts or "front" in low or "rear" in low:
                continue
            if all(not t for t in texts):
                continue
            if cells[0].attributes.get("colspan"):
                continue

            if len(texts) >= 3:
                tire_options.append(
                    {
                        "option_label": texts[0] or "Standard",
                        "front_tire": texts[1] or None,
                        "rear_tire": texts[2] or None,
                    }
                )
            elif len(texts) == 2:
                # 2-column variant: label + combined front/rear
                tire_options.append(
                    {
                        "option_label": texts[0] or "Standard",
                        "front_tire": texts[1] or None,
                        "rear_tire": None,
                    }
                )

        break  # Only parse the first matching table

    return tire_options


# ---------------------------------------------------------------------------
# Dimensions
# ---------------------------------------------------------------------------

_DIM_KEYS = {
    "wheelbase": ("wheelbase_in", "wheelbase_cm"),
    "length": ("length_in", "length_cm"),
    "width": ("width_in", "width_cm"),
    "height": ("height_in", "height_cm"),
    "weight": ("weight_lbs", "weight_kg"),
    "ground clearance": ("ground_clearance_in", "ground_clearance_cm"),
    "front tread": ("front_tread_in", "front_tread_cm"),
    "rear tread": ("rear_tread_in", "rear_tread_cm"),
}


def _parse_dimensions(html: HTMLParser) -> dict:
    """Extract the numeric dimensions from the standard key-value spec table."""
    dims: dict = {k: None for keys in _DIM_KEYS.values() for k in keys}

    for table in html.css("table.tdat"):
        for tr in table.css("tr"):
            cells = tr.css("td")
            if len(cells) < 2 or cells[0].attributes.get("colspan"):
                continue

            key = cells[0].text(strip=True).lower()
            value = cells[-1].text(strip=True)

            for pattern, (k1, k2) in _DIM_KEYS.items():
                if pattern in key:
                    if pattern == "weight":
                        v1, v2 = _lbs_kg(value)
                    else:
                        v1, v2 = _in_cm(value)
                    dims[k1] = v1
                    dims[k2] = v2
                    break

    return dims
