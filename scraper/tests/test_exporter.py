"""Unit tests for the JSON exporter serialisation helpers."""

from __future__ import annotations

import json
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from exporter import _default_serialiser, _SCHEMA_VERSION, write_model_json


class TestDefaultSerialiser:
    def test_decimal_to_float(self) -> None:
        assert _default_serialiser(Decimal("3.14")) == pytest.approx(3.14)

    def test_decimal_zero(self) -> None:
        assert _default_serialiser(Decimal("0")) == 0.0

    def test_datetime_to_iso(self) -> None:
        dt = datetime(2025, 6, 15, 12, 30, 0)
        assert _default_serialiser(dt) == "2025-06-15T12:30:00"

    def test_date_to_iso(self) -> None:
        d = date(2025, 6, 15)
        assert _default_serialiser(d) == "2025-06-15"

    def test_unknown_type_raises(self) -> None:
        with pytest.raises(TypeError):
            _default_serialiser(object())

    def test_schema_version_is_int(self) -> None:
        assert isinstance(_SCHEMA_VERSION, int)


class TestJsonSerialisationRoundTrip:
    """Verify that a document with Decimal + date values serialises cleanly."""

    def _make_document(self) -> dict:
        return {
            "schema_version": _SCHEMA_VERSION,
            "exported_at": "2025-06-15T00:00:00Z",
            "model": {
                "slug": "john-deere-6105m",
                "name": "John Deere 6105M",
                "horsepower_hp": Decimal("105.00"),
                "fuel_tank_l": Decimal("180.00"),
            },
            "engine": {
                "displacement_l": Decimal("6.788"),
                "rated_power_hp": Decimal("105.5"),
                "rated_rpm": 2100,
            },
            "tests": [
                {
                    "test_name": "Nebraska OECD Test",
                    "test_date_start": date(2015, 3, 1),
                    "test_date_end": date(2015, 4, 30),
                    "pto_max_hp": Decimal("112.43"),
                }
            ],
        }

    def test_serialises_without_error(self) -> None:
        doc = self._make_document()
        serialised = json.dumps(
            doc, default=_default_serialiser, indent=2, ensure_ascii=False
        )
        assert isinstance(serialised, str)

    def test_round_trip_decimals(self) -> None:
        doc = self._make_document()
        serialised = json.dumps(
            doc, default=_default_serialiser, indent=2, ensure_ascii=False
        )
        loaded = json.loads(serialised)
        assert loaded["model"]["horsepower_hp"] == pytest.approx(105.0)
        assert loaded["engine"]["displacement_l"] == pytest.approx(6.788)

    def test_round_trip_dates(self) -> None:
        doc = self._make_document()
        serialised = json.dumps(
            doc, default=_default_serialiser, indent=2, ensure_ascii=False
        )
        loaded = json.loads(serialised)
        assert loaded["tests"][0]["test_date_start"] == "2015-03-01"
        assert loaded["tests"][0]["test_date_end"] == "2015-04-30"

    def test_output_is_indented(self) -> None:
        doc = self._make_document()
        serialised = json.dumps(
            doc, default=_default_serialiser, indent=2, ensure_ascii=False
        )
        # Indented JSON has newlines
        assert "\n" in serialised
        # Top-level keys are indented with 2 spaces
        assert '  "schema_version"' in serialised


class TestWriteModelJson:
    def _make_document(self) -> dict:
        return {
            "schema_version": _SCHEMA_VERSION,
            "exported_at": "2025-06-15T00:00:00Z",
            "manufacturer": {"slug": "test-brand", "name": "Test Brand"},
            "series": None,
            "category": None,
            "model": {
                "slug": "test-brand-100",
                "name": "Test Brand 100",
                "horsepower_hp": 100.0,
            },
            "specifications": [],
            "engine": None,
            "tire_options": [],
            "tests": [],
            "photos": [],
        }

    def test_creates_file_at_expected_path(self, tmp_path: Path) -> None:
        doc = self._make_document()
        path = write_model_json(doc, tmp_path)
        assert path is not None
        assert path == tmp_path / "test-brand" / "test-brand-100.json"
        assert path.exists()

    def test_file_content_is_valid_json(self, tmp_path: Path) -> None:
        doc = self._make_document()
        path = write_model_json(doc, tmp_path)
        assert path is not None
        loaded = json.loads(path.read_text())
        assert loaded["model"]["slug"] == "test-brand-100"
        assert loaded["manufacturer"]["slug"] == "test-brand"

    def test_creates_manufacturer_subdirectory(self, tmp_path: Path) -> None:
        doc = self._make_document()
        write_model_json(doc, tmp_path)
        assert (tmp_path / "test-brand").is_dir()

    def test_overwrites_by_default(self, tmp_path: Path) -> None:
        doc = self._make_document()
        write_model_json(doc, tmp_path)
        doc["model"]["horsepower_hp"] = 999.0
        write_model_json(doc, tmp_path)
        loaded = json.loads((tmp_path / "test-brand" / "test-brand-100.json").read_text())
        assert loaded["model"]["horsepower_hp"] == pytest.approx(999.0)

    def test_skip_if_exists_returns_none_when_file_present(self, tmp_path: Path) -> None:
        doc = self._make_document()
        write_model_json(doc, tmp_path)
        result = write_model_json(doc, tmp_path, skip_if_exists=True)
        assert result is None

    def test_skip_if_exists_writes_when_file_absent(self, tmp_path: Path) -> None:
        doc = self._make_document()
        path = write_model_json(doc, tmp_path, skip_if_exists=True)
        assert path is not None
        assert path.exists()
