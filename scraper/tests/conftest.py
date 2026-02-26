"""Pytest fixtures shared across test modules."""

from __future__ import annotations

from pathlib import Path

import pytest
from selectolax.parser import HTMLParser

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def sample_manufacturer_html() -> HTMLParser:
    return HTMLParser((FIXTURES_DIR / "manufacturer_listing.html").read_text(encoding="utf-8"))


@pytest.fixture
def sample_series_html() -> HTMLParser:
    return HTMLParser((FIXTURES_DIR / "series_page.html").read_text(encoding="utf-8"))


@pytest.fixture
def sample_model_html() -> HTMLParser:
    return HTMLParser((FIXTURES_DIR / "model_page.html").read_text(encoding="utf-8"))
