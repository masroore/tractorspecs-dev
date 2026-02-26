from __future__ import annotations

import hashlib
import json
import re
import unicodedata


# ---------------------------------------------------------------------------
# Unit alias normalization maps
# ---------------------------------------------------------------------------

_UNIT_ALIASES: dict[str, str] = {
    "horsepower": "hp",
    "kilowatt": "kw",
    "kilowatts": "kw",
    "cubic centimeters": "cc",
    "cubic centimeter": "cc",
    "cubic inches": "ci",
    "cubic inch": "ci",
    "inches": "in",
    "inch": "in",
    "millimeters": "mm",
    "millimeter": "mm",
    "centimeters": "cm",
    "centimeter": "cm",
    "meters": "m",
    "meter": "m",
    "pounds": "lb",
    "pound": "lb",
    "kilograms": "kg",
    "kilogram": "kg",
    "gallons": "gal",
    "gallon": "gal",
    "liters": "l",
    "liter": "l",
    "litres": "l",
    "litre": "l",
    "rpm": "rpm",
    "revolutions per minute": "rpm",
    "psi": "psi",
    "bar": "bar",
    "nm": "nm",
    "newton-meters": "nm",
    "newton meters": "nm",
    "ft-lbs": "ft-lb",
    "ft-lb": "ft-lb",
    "foot-pounds": "ft-lb",
    "volt": "v",
    "volts": "v",
    "amp": "a",
    "amps": "a",
    "ampere": "a",
    "amperes": "a",
}

# Power-unit → multiplier to convert to hp
_TO_HP: dict[str, float] = {
    "kw": 1.34102,
    "ps": 0.98632,
    "cv": 0.98632,
    "pk": 0.98632,
    "ch": 0.98632,
}

# Pattern: leading numeric (with optional comma-thousands and decimal)
# followed by optional whitespace, then unit text, then optional parenthesized imperial/metric
_VALUE_UNIT_RE = re.compile(
    r"^([0-9][0-9,]*(?:\.[0-9]+)?)\s*([a-zA-Z/°\-]+)?",
)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def normalize_spec(key: str, value: str) -> tuple[str, str | None]:
    """Parse a raw spec value into a (normalized_value, unit) pair.

    Examples
    --------
    "75.5 hp"            → ("75.5", "hp")
    "1,498 cc"           → ("1498", "cc")
    "112.7 mm (4.4\")"   → ("112.7", "mm")
    "55.4 kW"            → ("74.3", "hp")     # converted to hp
    "3"                  → ("3", None)
    """
    cleaned = _clean_string(value)

    # Strip parenthesized secondary value, e.g. "112.7 mm (4.4")"
    cleaned = re.sub(r"\s*\(.*?\)", "", cleaned).strip()

    m = _VALUE_UNIT_RE.match(cleaned)
    if not m:
        # No leading number — return raw cleaned string, no unit
        return (cleaned, None)

    raw_number = m.group(1).replace(",", "")  # remove thousands separator
    raw_unit = (m.group(2) or "").strip().lower()
    unit = _normalize_unit(raw_unit) if raw_unit else None

    # Convert power units to hp
    if unit in _TO_HP:
        try:
            hp_value = float(raw_number) * _TO_HP[unit]
            return (f"{hp_value:.2f}", "hp")
        except ValueError:
            pass

    return (raw_number, unit if unit else None)


def compute_spec_hash(specs: list[dict]) -> str:
    """Return a SHA-256 hex digest of the canonical spec set.

    The hash is stable regardless of dict key ordering or list ordering.
    Use it to detect whether a model page has changed since last crawl.
    """
    canonical = json.dumps(
        sorted(specs, key=lambda x: (x.get("group", ""), x.get("key", ""))),
        sort_keys=True,
        ensure_ascii=False,
    )
    return hashlib.sha256(canonical.encode()).hexdigest()


def build_slug(name: str) -> str:
    """Convert a human-readable name into a URL-friendly slug.

    Examples
    --------
    "John Deere 1025R"     → "john-deere-1025r"
    "Massey Ferguson 6S.180" → "massey-ferguson-6s-180"
    "AGCO 50 HP (4x4)"     → "agco-50-hp-4x4"
    """
    name = name.strip()
    # Normalize Unicode (NFD → drop combining marks)
    name = unicodedata.normalize("NFD", name)
    name = "".join(c for c in name if unicodedata.category(c) != "Mn")
    # Lower-case
    name = name.lower()
    # Replace common substitutions
    name = name.replace("&", "and")
    name = name.replace("+", "plus")
    # Replace all non-alphanumeric chars (including dots, parens, spaces) with dash
    name = re.sub(r"[^a-z0-9]+", "-", name)
    # Collapse multiple dashes
    name = re.sub(r"-{2,}", "-", name)
    # Strip leading/trailing dashes
    return name.strip("-")


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------


def _clean_string(value: str) -> str:
    """Strip non-breaking spaces, extra whitespace, and HTML entities."""
    value = value.replace("\u202f", "")  # narrow no-break space (thousands separator)
    value = value.replace("\u00a0", " ")  # non-breaking space
    value = value.replace("\xa0", " ")
    value = value.replace("&nbsp;", " ")
    value = value.replace("&amp;", "&")
    value = value.replace("&lt;", "<")
    value = value.replace("&gt;", ">")
    return value.strip()


def _normalize_unit(unit: str) -> str:
    """Map verbose unit strings to canonical short forms."""
    unit = unit.lower().strip(" .")
    return _UNIT_ALIASES.get(unit, unit)
