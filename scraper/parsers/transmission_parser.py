"""Parse the transmission sub-page (*-transmission.html) from TractorData.com.

The page contains a ``table.tdat`` with one group ("Transmission") and a few
key-value rows such as:

    Transmission  | Vario
    Gears         | infinite forward and reverse

Returned dict shape
-------------------
{
    "transmission_name": str | None,
    "gear_type":         str | None,
    "speeds_image_url":  str | None,   # relative URL of the speeds diagram
    "raw_data":          dict,
}
"""

from __future__ import annotations

import re

from selectolax.parser import HTMLParser


def parse_transmission_page(html: HTMLParser) -> dict:
    """Return a structured transmission dict from the transmission sub-page."""
    result: dict = {
        "transmission_name": None,
        "gear_type": None,
        "speeds_image_url": None,
        "raw_data": {},
    }
    raw: dict[str, str] = {}

    for tr in html.css("table.tdat tr"):
        cells = tr.css("td")

        # Check for an image cell (speeds diagram)
        for img in tr.css("img"):
            src = img.attributes.get("src", "")
            if "speed" in src.lower() or "transmission" in src.lower():
                result["speeds_image_url"] = src

        if len(cells) < 2:
            continue
        if cells[0].attributes.get("colspan"):
            continue

        key = cells[0].text(strip=True)
        value = cells[-1].text(strip=True)

        if not key or not value:
            continue

        key_lo = key.lower()

        if "transmission" in key_lo:
            result["transmission_name"] = value
        elif "gear" in key_lo or "speed" in key_lo or "forward" in value.lower():
            result["gear_type"] = value
        else:
            raw[key] = value

    result["raw_data"] = raw
    return result
