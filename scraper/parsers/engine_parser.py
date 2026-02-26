"""Parse the engine sub-page (*-engine.html) from TractorData.com.

The page contains a single ``table.tdat`` whose rows are either
group-header rows (``<td colspan="2">``) or key-value rows
(``<td class="tdata"> … <td class="tdata2">``).

Returned dict shape
-------------------
{
    "engine_manufacturer":  str | None,
    "fuel_type":            str | None,
    "cylinders":            int | None,
    "cooling":              str | None,
    "displacement_ci":      float | None,
    "displacement_l":       float | None,
    "bore_in":              float | None,
    "bore_mm":              float | None,
    "stroke_in":            float | None,
    "stroke_mm":            float | None,
    "emissions_tier":       str | None,
    "emission_control":     str | None,
    "rated_power_hp":       float | None,
    "rated_power_kw":       float | None,
    "rated_rpm":            int | None,
    "torque_lbft":          float | None,
    "torque_nm":            float | None,
    "torque_rpm":           int | None,
    "starter_type":         str | None,
    "starter_volts":        float | None,
    "starter_hp":           float | None,
    "oil_change_hours":     int | None,
    "raw_data":             dict,          # leftover key-value pairs
}
"""

from __future__ import annotations

import re

from selectolax.parser import HTMLParser, Node


# ---------------------------------------------------------------------------
# Regex helpers
# ---------------------------------------------------------------------------

_FLOAT_RE = re.compile(r"[\d,]+\.?\d*")
_CI_L_RE = re.compile(r"([\d.]+)\s*ci\s*/\s*([\d.]+)\s*[Ll]", re.I)
_IN_MM_RE = re.compile(r"([\d.]+)\s*in\s*/\s*([\d.]+)\s*mm", re.I)
_HP_KW_RE = re.compile(r"([\d.]+)\s*hp\s*/\s*([\d.]+)\s*kw", re.I)
_LBFT_NM_RE = re.compile(r"([\d.]+)\s*lb-ft\s*/\s*([\d.]+)\s*Nm", re.I)
_RPM_RE = re.compile(r"([\d,]+)\s*rpm", re.I)
_VOLTS_RE = re.compile(r"([\d.]+)\s*[Vv](?:olt)?")
_STARTER_HP_RE = re.compile(r"([\d.]+)\s*hp", re.I)


def _first_float(text: str) -> float | None:
    m = _FLOAT_RE.search(text.replace(",", ""))
    return float(m.group()) if m else None


# ---------------------------------------------------------------------------
# Main parser
# ---------------------------------------------------------------------------


def parse_engine_page(html: HTMLParser) -> dict:
    """Return a structured engine dict from the engine sub-page HTML."""
    rows = _collect_rows(html)
    result: dict = {
        k: None
        for k in (
            "engine_manufacturer",
            "fuel_type",
            "cylinders",
            "cooling",
            "displacement_ci",
            "displacement_l",
            "bore_in",
            "bore_mm",
            "stroke_in",
            "stroke_mm",
            "emissions_tier",
            "emission_control",
            "rated_power_hp",
            "rated_power_kw",
            "rated_rpm",
            "torque_lbft",
            "torque_nm",
            "torque_rpm",
            "starter_type",
            "starter_volts",
            "starter_hp",
            "oil_change_hours",
        )
    }
    raw: dict[str, str] = {}

    for key_raw, value_raw in rows:
        key_lo = key_raw.lower().strip()
        value = value_raw.strip()

        if "engine manufacturer" in key_lo:
            result["engine_manufacturer"] = value

        elif key_lo in ("fuel", "fuel type", "engine fuel"):
            result["fuel_type"] = value

        elif "cylinder" in key_lo:
            m = _FLOAT_RE.search(value.replace(",", ""))
            result["cylinders"] = int(m.group()) if m else None

        elif "cooling" in key_lo:
            result["cooling"] = value

        elif "displacement" in key_lo:
            m = _CI_L_RE.search(value)
            if m:
                result["displacement_ci"] = float(m.group(1))
                result["displacement_l"] = float(m.group(2))
            else:
                result["displacement_ci"] = _first_float(value)

        elif "bore" in key_lo and "stroke" in key_lo:
            # "Bore/Stroke: 4.96×6.54 in / 126×166 mm" — find all floats
            floats = _FLOAT_RE.findall(value.replace(",", ""))
            if len(floats) >= 4:
                result["bore_in"] = float(floats[0])
                result["stroke_in"] = float(floats[1])
                result["bore_mm"] = float(floats[2])
                result["stroke_mm"] = float(floats[3])
            elif len(floats) == 2:
                result["bore_in"] = float(floats[0])
                result["stroke_in"] = float(floats[1])

        elif "bore" in key_lo:
            m = _IN_MM_RE.search(value)
            if m:
                result["bore_in"] = float(m.group(1))
                result["bore_mm"] = float(m.group(2))

        elif "stroke" in key_lo:
            m = _IN_MM_RE.search(value)
            if m:
                result["stroke_in"] = float(m.group(1))
                result["stroke_mm"] = float(m.group(2))

        elif (
            "emission tier" in key_lo or "emissions tier" in key_lo or key_lo == "tier"
        ):
            result["emissions_tier"] = value

        elif "emission control" in key_lo:
            result["emission_control"] = value

        elif "power" in key_lo or "rated hp" in key_lo or "net power" in key_lo:
            m = _HP_KW_RE.search(value)
            if m:
                result["rated_power_hp"] = float(m.group(1))
                result["rated_power_kw"] = float(m.group(2))
            elif not result["rated_power_hp"]:
                f = _first_float(value)
                if f:
                    result["rated_power_hp"] = f

        elif "rated rpm" in key_lo or "engine rpm" in key_lo:
            m = _RPM_RE.search(value)
            if m:
                result["rated_rpm"] = int(m.group(1).replace(",", ""))

        elif "torque" in key_lo and "rpm" not in key_lo:
            m = _LBFT_NM_RE.search(value)
            if m:
                result["torque_lbft"] = float(m.group(1))
                result["torque_nm"] = float(m.group(2))
            else:
                result["torque_lbft"] = _first_float(value)

        elif "torque rpm" in key_lo or ("torque" in key_lo and "rpm" in key_lo):
            m = _RPM_RE.search(value)
            if m:
                result["torque_rpm"] = int(m.group(1).replace(",", ""))

        elif "starter" in key_lo:
            # "electric, 12V, 9.4 hp / 7.0 kW"
            if "electric" in value.lower():
                result["starter_type"] = "electric"
            elif "air" in value.lower():
                result["starter_type"] = "air"
            else:
                result["starter_type"] = value.split(",")[0].strip()

            mv = _VOLTS_RE.search(value)
            if mv:
                result["starter_volts"] = float(mv.group(1))

            mh = _STARTER_HP_RE.search(value)
            if mh:
                result["starter_hp"] = float(mh.group(1))

        elif "oil" in key_lo and ("hour" in key_lo or "change" in key_lo):
            m = _FLOAT_RE.search(value.replace(",", ""))
            result["oil_change_hours"] = int(float(m.group())) if m else None

        else:
            raw[key_raw] = value

    result["raw_data"] = raw
    return result


# ---------------------------------------------------------------------------
# HTML helpers
# ---------------------------------------------------------------------------


def _collect_rows(html: HTMLParser) -> list[tuple[str, str]]:
    """Return [(key, value), ...] from all key-value rows in the spec table."""
    rows: list[tuple[str, str]] = []

    for tr in html.css("table.tdat tr"):
        cells = tr.css("td")
        if len(cells) < 2:
            continue
        # Skip group-header rows (single cell spanning 2 columns)
        if cells[0].attributes.get("colspan"):
            continue

        key = cells[0].text(strip=True)
        value = cells[-1].text(strip=True)

        if key and value:
            rows.append((key, value))

    return rows
