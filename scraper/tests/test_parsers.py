"""Tests for HTML parsers — manufacturer listing, series page, model page."""

from __future__ import annotations

import pytest

from parsers.manufacturer_parser import parse_manufacturer_listing
from parsers.model_parser import parse_model_page
from parsers.series_parser import parse_manufacturer_page


class TestManufacturerParser:
    def test_returns_list(self, sample_manufacturer_html: "HTMLParser") -> None:
        results = parse_manufacturer_listing(sample_manufacturer_html)
        assert isinstance(results, list)
        assert len(results) > 0

    def test_each_item_has_required_keys(
        self, sample_manufacturer_html: "HTMLParser"
    ) -> None:
        results = parse_manufacturer_listing(sample_manufacturer_html)
        for item in results:
            assert "name" in item
            assert "slug" in item
            assert "url" in item

    def test_names_non_empty(self, sample_manufacturer_html: "HTMLParser") -> None:
        results = parse_manufacturer_listing(sample_manufacturer_html)
        for item in results:
            assert item["name"].strip() != ""

    def test_slugs_non_empty(self, sample_manufacturer_html: "HTMLParser") -> None:
        results = parse_manufacturer_listing(sample_manufacturer_html)
        for item in results:
            assert item["slug"].strip() != ""

    def test_known_manufacturer_present(
        self, sample_manufacturer_html: "HTMLParser"
    ) -> None:
        results = parse_manufacturer_listing(sample_manufacturer_html)
        names = [r["name"].lower() for r in results]
        assert any("john deere" in n for n in names)


class TestSeriesParser:
    def test_returns_dict_with_keys(self, sample_series_html: "HTMLParser") -> None:
        result = parse_manufacturer_page(sample_series_html)
        assert "manufacturer" in result
        assert "series" in result

    def test_manufacturer_has_description(
        self, sample_series_html: "HTMLParser"
    ) -> None:
        result = parse_manufacturer_page(sample_series_html)
        assert result["manufacturer"].get("description", "") != ""

    def test_series_is_list(self, sample_series_html: "HTMLParser") -> None:
        result = parse_manufacturer_page(sample_series_html)
        assert isinstance(result["series"], list)
        assert len(result["series"]) > 0

    def test_each_series_has_name_and_models(
        self, sample_series_html: "HTMLParser"
    ) -> None:
        result = parse_manufacturer_page(sample_series_html)
        for series in result["series"]:
            assert "name" in series
            assert "models" in series
            assert isinstance(series["models"], list)

    def test_model_entries_have_url(self, sample_series_html: "HTMLParser") -> None:
        result = parse_manufacturer_page(sample_series_html)
        for series in result["series"]:
            for model in series["models"]:
                assert "url" in model
                assert model["url"].strip() != ""


class TestModelParser:
    def test_returns_dict_with_name(self, sample_model_html: "HTMLParser") -> None:
        result = parse_model_page(sample_model_html)
        assert "name" in result
        assert result["name"] != ""

    def test_name_contains_model(self, sample_model_html: "HTMLParser") -> None:
        result = parse_model_page(sample_model_html)
        assert "1025R" in result["name"]

    def test_production_years_extracted(self, sample_model_html: "HTMLParser") -> None:
        result = parse_model_page(sample_model_html)
        assert result.get("production_start_year") == 2012
        assert result.get("production_end_year") == 2023

    def test_specs_is_list(self, sample_model_html: "HTMLParser") -> None:
        result = parse_model_page(sample_model_html)
        assert isinstance(result.get("specs"), list)
        assert len(result["specs"]) > 0

    def test_spec_groups_present(self, sample_model_html: "HTMLParser") -> None:
        result = parse_model_page(sample_model_html)
        groups = {s["group"] for s in result["specs"]}
        assert "Engine" in groups

    def test_hp_extracted(self, sample_model_html: "HTMLParser") -> None:
        result = parse_model_page(sample_model_html)
        hp = result.get("horsepower_hp")
        assert hp is not None
        assert float(hp) > 0

    def test_missing_production_years_handled_gracefully(self) -> None:
        from selectolax.parser import HTMLParser

        html = HTMLParser("<html><body><h1>Acme 100</h1></body></html>")
        result = parse_model_page(html)
        assert result.get("production_start_year") is None
        assert result.get("production_end_year") is None

    def test_all_spec_items_have_required_keys(
        self, sample_model_html: "HTMLParser"
    ) -> None:
        result = parse_model_page(sample_model_html)
        for spec in result["specs"]:
            assert "group" in spec
            assert "key" in spec
            assert "value" in spec
            assert "display_order" in spec
