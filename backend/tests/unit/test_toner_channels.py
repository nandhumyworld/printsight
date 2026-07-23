"""Tests for toner coverage-channel helpers."""

from __future__ import annotations

from app.services.cost_calc import _COLOR_MAP
from app.services.toner_channels import (
    CHANNEL_KEYS,
    COVERAGE_COLUMN_BY_CHANNEL,
    backfill_channel,
    validate_coverage_channel,
)


def test_channel_keys_match_cost_calc_color_map():
    assert CHANNEL_KEYS == set(_COLOR_MAP)


def test_coverage_columns_match_cost_calc():
    for key, col in COVERAGE_COLUMN_BY_CHANNEL.items():
        assert col == _COLOR_MAP[key][0]


def test_backfill_known_names():
    assert backfill_channel("Black") == "K"
    assert backfill_channel("cyan") == "C"
    assert backfill_channel("Gold") == "GLD"
    assert backfill_channel("GLD #1") == "GLD"
    assert backfill_channel("K") == "K"
    assert backfill_channel("Texture") == "CR"


def test_backfill_unknown_returns_none():
    assert backfill_channel("Chartreuse") is None
    assert backfill_channel("") is None


def test_validate_ok_when_mapped():
    mapping = {"coverage_k": "Raster Coverage K"}
    assert validate_coverage_channel("K", mapping) is None


def test_validate_rejects_unknown_channel():
    assert validate_coverage_channel("ZZ", {"coverage_k": "x"}) is not None


def test_validate_rejects_unmapped_column():
    assert validate_coverage_channel("K", {"color_pages": "x"}) is not None
    assert validate_coverage_channel("K", None) is not None
