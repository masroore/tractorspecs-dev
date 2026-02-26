"""Pytest fixtures shared across test modules."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def sample_manufacturer_html() -> str:
    return (FIXTURES_DIR / "manufacturer_listing.html").read_text(encoding="utf-8")


@pytest.fixture
def sample_series_html() -> str:
    return (FIXTURES_DIR / "series_page.html").read_text(encoding="utf-8")


@pytest.fixture
def sample_model_html() -> str:
    return (FIXTURES_DIR / "model_page.html").read_text(encoding="utf-8")
