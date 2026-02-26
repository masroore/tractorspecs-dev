"""Unit tests for the importer helpers."""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from importer import _discover_files, import_files


# ---------------------------------------------------------------------------
# File discovery
# ---------------------------------------------------------------------------


class TestDiscoverFiles:
    def test_finds_json_files_recursively(self, tmp_path: Path) -> None:
        (tmp_path / "john-deere").mkdir()
        (tmp_path / "john-deere" / "john-deere-6105m.json").write_text("{}")
        (tmp_path / "john-deere" / "john-deere-6110.json").write_text("{}")
        (tmp_path / "kubota").mkdir()
        (tmp_path / "kubota" / "kubota-m110a.json").write_text("{}")

        files = _discover_files(tmp_path)
        assert len(files) == 3
        assert all(f.suffix == ".json" for f in files)

    def test_ignores_non_json_files(self, tmp_path: Path) -> None:
        (tmp_path / "readme.txt").write_text("hello")
        (tmp_path / "model.json").write_text("{}")

        files = _discover_files(tmp_path)
        assert len(files) == 1
        assert files[0].name == "model.json"

    def test_returns_sorted_list(self, tmp_path: Path) -> None:
        (tmp_path / "z.json").write_text("{}")
        (tmp_path / "a.json").write_text("{}")
        (tmp_path / "m.json").write_text("{}")

        files = _discover_files(tmp_path)
        names = [f.name for f in files]
        assert names == sorted(names)

    def test_empty_directory(self, tmp_path: Path) -> None:
        assert _discover_files(tmp_path) == []


# ---------------------------------------------------------------------------
# Minimal valid JSON document fixture
# ---------------------------------------------------------------------------


def _make_valid_document() -> dict:
    return {
        "schema_version": 1,
        "exported_at": "2025-06-15T00:00:00Z",
        "manufacturer": {
            "slug": "john-deere",
            "name": "John Deere",
            "country": "USA",
            "description": None,
            "founded_year": 1837,
            "logo_path": None,
        },
        "series": None,
        "category": None,
        "model": {
            "slug": "john-deere-6105m",
            "name": "John Deere 6105M",
            "tractor_type": "farm",
            "production_start_year": 2012,
            "production_end_year": 2019,
            "horsepower_hp": 105.0,
            "description": "A mid-range utility tractor.",
            "drive_type": "4WD",
            "steering_type": None,
            "brake_type": None,
            "cab_description": None,
            "fuel_tank_l": 180.0,
            "def_tank_l": None,
            "seo_title": None,
            "seo_description": None,
        },
        "specifications": [
            {
                "spec_group": "Engine",
                "spec_key": "Engine HP",
                "spec_value": "105",
                "unit": "hp",
                "display_order": 0,
            }
        ],
        "engine": {
            "engine_manufacturer": "John Deere",
            "fuel_type": "diesel",
            "cylinders": 4,
            "cooling": "liquid",
            "displacement_ci": None,
            "displacement_l": 4.5,
            "bore_in": None,
            "bore_mm": None,
            "stroke_in": None,
            "stroke_mm": None,
            "emissions_tier": "Tier 4B",
            "emission_control": None,
            "rated_power_hp": 105.0,
            "rated_power_kw": 78.3,
            "rated_rpm": 2100,
            "torque_lbft": None,
            "torque_nm": None,
            "torque_rpm": None,
            "starter_type": None,
            "starter_volts": None,
            "starter_hp": None,
            "oil_change_hours": 500,
            "raw_data": {},
        },
        "tire_options": [
            {
                "option_label": "Standard",
                "front_tire": "11.2-24",
                "rear_tire": "18.4-34",
                "wheelbase_in": 90.9,
                "wheelbase_cm": 231.0,
                "length_in": None,
                "length_cm": None,
                "width_in": None,
                "width_cm": None,
                "height_in": None,
                "height_cm": None,
                "weight_lbs": 9259.0,
                "weight_kg": 4200.0,
                "ground_clearance_in": None,
                "ground_clearance_cm": None,
                "front_tread_in": None,
                "front_tread_cm": None,
                "rear_tread_in": None,
                "rear_tread_cm": None,
                "display_order": 0,
            }
        ],
        "tests": [
            {
                "test_name": "Nebraska OECD Test 2093",
                "test_date_start": "2015-03-01",
                "test_date_end": "2015-04-30",
                "test_url": "https://tractortest.unl.edu/2093",
                "pto_max_hp": 112.43,
                "pto_max_kw": 83.84,
                "pto_max_fuel_gph": 8.1,
                "pto_rated_eng_hp": 107.1,
                "pto_rated_eng_kw": 79.87,
                "pto_rated_pto_hp": 103.3,
                "pto_rated_pto_kw": 77.0,
                "drawbar_max_hp": 95.5,
                "drawbar_max_kw": 71.2,
                "drawbar_max_fuel_gph": 7.9,
                "drawbar_max_pull_lbs": 14200.0,
                "drawbar_max_pull_kg": 6441.0,
                "raw_data": {},
            }
        ],
        "photos": [
            {
                "image_url": "https://tractordata.com/photos/john-deere-6105m.jpg",
                "attribution": "TractorData.com",
                "display_order": 0,
            }
        ],
    }


# ---------------------------------------------------------------------------
# import_files — dry-run (no DB needed)
# ---------------------------------------------------------------------------


class TestImportFilesDryRun:
    @pytest.mark.asyncio
    async def test_dry_run_does_not_call_upsert(self, tmp_path: Path) -> None:
        doc = _make_valid_document()
        json_path = tmp_path / "model.json"
        json_path.write_text(json.dumps(doc, indent=2), encoding="utf-8")

        mock_pool = MagicMock()

        with (
            patch("importer.upsert_manufacturer", new_callable=AsyncMock) as mock_mfr,
            patch("importer.upsert_model", new_callable=AsyncMock) as mock_model,
        ):
            succeeded, failed = await import_files(mock_pool, [json_path], dry_run=True)

        assert succeeded == 1
        assert failed == 0
        mock_mfr.assert_not_called()
        mock_model.assert_not_called()

    @pytest.mark.asyncio
    async def test_dry_run_invalid_json_counts_as_failed(self, tmp_path: Path) -> None:
        bad_path = tmp_path / "bad.json"
        bad_path.write_text("not valid json", encoding="utf-8")

        mock_pool = MagicMock()
        succeeded, failed = await import_files(mock_pool, [bad_path], dry_run=True)

        assert succeeded == 0
        assert failed == 1

    @pytest.mark.asyncio
    async def test_dry_run_warns_on_unknown_schema_version(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        doc = _make_valid_document()
        doc["schema_version"] = 99
        json_path = tmp_path / "model.json"
        json_path.write_text(json.dumps(doc, indent=2), encoding="utf-8")

        mock_pool = MagicMock()
        succeeded, failed = await import_files(mock_pool, [json_path], dry_run=True)

        assert succeeded == 1
        assert failed == 0

    @pytest.mark.asyncio
    async def test_dry_run_multiple_files(self, tmp_path: Path) -> None:
        doc = _make_valid_document()
        for i in range(3):
            doc["model"]["slug"] = f"model-{i}"
            (tmp_path / f"model-{i}.json").write_text(json.dumps(doc, indent=2), encoding="utf-8")

        mock_pool = MagicMock()
        succeeded, failed = await import_files(
            mock_pool, list(tmp_path.glob("*.json")), dry_run=True
        )

        assert succeeded == 3
        assert failed == 0
