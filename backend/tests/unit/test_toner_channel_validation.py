"""Coverage-channel validation used by the toner endpoints."""

from __future__ import annotations

from app.services.toner_channels import validate_coverage_channel


def test_valid_channel_for_mapped_printer():
    mapping = {"coverage_gld_1": "Raster Coverage GLD #1"}
    assert validate_coverage_channel("GLD", mapping) is None


def test_channel_not_mapped_is_rejected():
    mapping = {"coverage_k": "Raster Coverage K"}
    msg = validate_coverage_channel("GLD", mapping)
    assert msg is not None and "not mapped" in msg


def test_bad_channel_is_rejected():
    assert validate_coverage_channel("NOPE", {"coverage_k": "x"}) is not None
