"""Tests for transformer.py — spec normalisation, slug building, hash stability."""

from __future__ import annotations

import pytest

from transformer import build_slug, compute_spec_hash, normalize_spec


class TestNormalizeSpec:
    def test_plain_hp(self) -> None:
        value, unit = normalize_spec("Engine HP", "25.0 hp")
        assert value == "25.0"
        assert unit == "hp"

    def test_cc_with_comma(self) -> None:
        value, unit = normalize_spec("Displacement", "1,498 cc")
        assert value == "1498"
        assert unit == "cc"

    def test_mm_with_imperial_suffix(self) -> None:
        value, unit = normalize_spec("Bore", '87.0 mm (3.4")')
        assert value == "87.0"
        assert unit == "mm"

    def test_kw_to_hp(self) -> None:
        value, unit = normalize_spec("Power", "55.4 kW")
        assert unit == "hp"
        hp = float(value)
        assert abs(hp - 55.4 * 1.341) < 0.1

    def test_ps_to_hp(self) -> None:
        value, unit = normalize_spec("Power", "100 PS")
        assert unit == "hp"
        hp = float(value)
        assert abs(hp - 100 * 0.98632) < 0.1

    def test_cv_to_hp(self) -> None:
        value, unit = normalize_spec("Power", "75 CV")
        assert unit == "hp"
        hp = float(value)
        assert abs(hp - 75 * 0.98632) < 0.1

    def test_plain_string_no_unit(self) -> None:
        value, unit = normalize_spec("Fuel Type", "Diesel")
        assert value == "Diesel"
        assert unit is None

    def test_strips_non_breaking_space(self) -> None:
        value, unit = normalize_spec("Weight", "1\u202f534 lb")
        assert unit == "lb"

    def test_empty_value(self) -> None:
        value, unit = normalize_spec("Something", "")
        assert value == ""
        assert unit is None


class TestBuildSlug:
    def test_basic(self) -> None:
        assert build_slug("John Deere 1025R") == "john-deere-1025r"

    def test_ampersand(self) -> None:
        assert build_slug("Massey & Ferguson") == "massey-and-ferguson"

    def test_special_chars_stripped(self) -> None:
        slug = build_slug("Bühler Versatile")
        assert " " not in slug
        assert slug == slug.lower()

    def test_collapses_multiple_dashes(self) -> None:
        slug = build_slug("foo  --  bar")
        assert "--" not in slug
        assert slug == "foo-bar"

    def test_leading_trailing_dashes_removed(self) -> None:
        slug = build_slug("  -hello-  ")
        assert not slug.startswith("-")
        assert not slug.endswith("-")


class TestComputeSpecHash:
    def test_stable(self) -> None:
        specs = [
            {
                "group": "Engine",
                "key": "HP",
                "value": "25.0",
                "unit": "hp",
                "display_order": 0,
            },
            {
                "group": "Engine",
                "key": "Cylinders",
                "value": "3",
                "unit": None,
                "display_order": 1,
            },
        ]
        assert compute_spec_hash(specs) == compute_spec_hash(specs)

    def test_order_independent(self) -> None:
        s1 = [
            {"group": "B", "key": "x", "value": "1", "unit": None, "display_order": 0},
            {"group": "A", "key": "y", "value": "2", "unit": None, "display_order": 0},
        ]
        s2 = list(reversed(s1))
        assert compute_spec_hash(s1) == compute_spec_hash(s2)

    def test_different_values_differ(self) -> None:
        s1 = [
            {
                "group": "Engine",
                "key": "HP",
                "value": "25.0",
                "unit": "hp",
                "display_order": 0,
            }
        ]
        s2 = [
            {
                "group": "Engine",
                "key": "HP",
                "value": "30.0",
                "unit": "hp",
                "display_order": 0,
            }
        ]
        assert compute_spec_hash(s1) != compute_spec_hash(s2)
