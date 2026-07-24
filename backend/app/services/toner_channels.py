"""Toner coverage-channel catalog and helpers.

A "coverage channel" is the key tying a toner to the raster-coverage database
column its cost is computed from. Keys mirror cost_calc._COLOR_MAP.
"""

from __future__ import annotations

from typing import Optional

# channel key -> raster-coverage column on print_jobs
COVERAGE_COLUMN_BY_CHANNEL: dict[str, str] = {
    "K": "coverage_k",
    "C": "coverage_c",
    "M": "coverage_m",
    "Y": "coverage_y",
    "GLD": "coverage_gld_1",
    "SLV": "coverage_slv_1",
    "CLR": "coverage_clr_1",
    "WHT": "coverage_wht_1",
    "CR": "coverage_cr_1",
    "P": "coverage_p_1",
    "PA": "coverage_pa_1",
    "GLD_6": "coverage_gld_6",
    "SLV_6": "coverage_slv_6",
    "WHT_6": "coverage_wht_6",
    "P_6": "coverage_p_6",
}

CHANNEL_KEYS = frozenset(COVERAGE_COLUMN_BY_CHANNEL)

# free-text toner_color (uppercased) -> channel, for backfilling legacy rows
_BACKFILL: dict[str, str] = {
    "BLACK": "K", "K": "K",
    "CYAN": "C", "C": "C",
    "MAGENTA": "M", "M": "M",
    "YELLOW": "Y", "Y": "Y",
    "GOLD": "GLD", "GLD": "GLD", "GLD #1": "GLD",
    "SILVER": "SLV", "SLV": "SLV", "SLV #1": "SLV",
    "CLEAR": "CLR", "CLR": "CLR", "CLR #1": "CLR",
    "WHITE": "WHT", "WHT": "WHT", "WHT #1": "WHT",
    "TEXTURE": "CR", "CR": "CR", "CR #1": "CR",
    "PINK": "P", "P": "P", "P #1": "P",
    "PA": "PA", "PA #1": "PA",
    "GLD #6": "GLD_6",
    "SLV #6": "SLV_6",
    "WHT #6": "WHT_6",
    "P #6": "P_6",
}


def backfill_channel(toner_color: str) -> Optional[str]:
    """Map a legacy free-text toner_color to a channel key, or None."""
    return _BACKFILL.get((toner_color or "").strip().upper())


def validate_coverage_channel(
    channel: str, column_mapping: Optional[dict]
) -> Optional[str]:
    """Return an error message if the channel is invalid for this printer, else None."""
    if channel not in CHANNEL_KEYS:
        return f"Unknown coverage channel '{channel}'."
    col = COVERAGE_COLUMN_BY_CHANNEL[channel]
    if not column_mapping or col not in column_mapping:
        return f"Coverage column '{col}' is not mapped for this printer."
    return None
