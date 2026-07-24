"""Unit tests for cost calculation engine."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace

import pytest

from app.services.cost_calc import apply_cost_to_job, compute_job_cost, match_paper_for_job


def _toner(color, price=300, yield_pages=10000, ref_cov=Decimal("5.00")):
    return SimpleNamespace(
        id=1,
        printer_id=1,
        toner_color=color,
        price_per_unit=Decimal(str(price)),
        rated_yield_pages=yield_pages,
        reference_coverage_pct=ref_cov,
        replacement_logs=[],
    )


def _paper(name="Plain 80", width=210, length=297, gsm_min=78, gsm_max=82,
           price=Decimal("0.50"), multiplier=Decimal("1.00"), tol_w=2, tol_l=2):
    return SimpleNamespace(
        id=1, name=name, width_mm=Decimal(str(width)), length_mm=Decimal(str(length)),
        gsm_min=gsm_min, gsm_max=gsm_max, price_per_sheet=price,
        counter_multiplier=multiplier,
        width_tolerance_mm=Decimal(str(tol_w)), length_tolerance_mm=Decimal(str(tol_l)),
    )


def _job(**overrides):
    base = dict(
        id=1, printer_id=1,
        recorded_at=datetime(2026, 4, 20, tzinfo=timezone.utc),
        paper_type="Plain 80", paper_width_mm=Decimal("210"),
        paper_length_mm=Decimal("297"), paper_gsm=80,
        printed_sheets=100, color_pages=50, bw_pages=50,
        gold_pages=0, silver_pages=0, clear_pages=0, white_pages=0,
        texture_pages=0, pink_pages=0, pa_pages=0,
        gold_6_pages=0, silver_6_pages=0, white_6_pages=0, pink_6_pages=0,
        coverage_k=Decimal("5.0"), coverage_c=Decimal("5.0"),
        coverage_m=Decimal("5.0"), coverage_y=Decimal("5.0"),
        coverage_est_k=None, coverage_est_c=None,
        coverage_est_m=None, coverage_est_y=None,
        coverage_gld_1=None, coverage_slv_1=None, coverage_clr_1=None,
        coverage_wht_1=None, coverage_cr_1=None, coverage_p_1=None,
        coverage_pa_1=None, coverage_gld_6=None, coverage_slv_6=None,
        coverage_wht_6=None, coverage_p_6=None,
        coverage_est_gld_1=None, coverage_est_slv_1=None,
        coverage_est_clr_1=None, coverage_est_wht_1=None,
        coverage_est_cr_1=None, coverage_est_p_1=None,
        coverage_est_pa_1=None, coverage_est_gld_6=None,
        coverage_est_slv_6=None, coverage_est_wht_6=None,
        coverage_est_p_6=None,
    )
    base.update(overrides)
    return SimpleNamespace(**base)


def test_paper_match_exact_name_and_dims():
    j = _job()
    papers = [_paper()]
    matched = match_paper_for_job(j, papers)
    assert matched is not None and matched.name == "Plain 80"


def test_paper_no_match_returns_none():
    j = _job(paper_type="Unknown", paper_width_mm=Decimal("500"))
    papers = [_paper()]
    assert match_paper_for_job(j, papers) is None


def test_toner_cost_at_exact_reference_coverage():
    # 5% on each CMYK. Coverage is the job total, so pages are NOT multiplied in.
    # price_per_page = 300 / 10000 = 0.03
    # each color cost = (5/5) * 0.03 = 0.03 → total toner = 0.03 * 4 = 0.12
    j = _job()
    toners = [_toner("K"), _toner("C"), _toner("M"), _toner("Y")]
    result = compute_job_cost(j, toners=toners, matched_paper=_paper())
    assert result["toner_cost"] == pytest.approx(0.12, abs=0.01)


def test_toner_cost_scales_with_coverage():
    # Double coverage → double the K toner cost.
    j = _job(coverage_k=Decimal("10.0"))
    toners = [_toner("K"), _toner("C"), _toner("M"), _toner("Y")]
    result = compute_job_cost(j, toners=toners, matched_paper=_paper())
    # K was 0.03 at 5%, now 0.06 at 10%.
    assert result["per_channel_cost"]["coverage_est_k"] == pytest.approx(0.06, abs=0.01)


def test_coverage_is_job_total_not_multiplied_by_pages():
    # Raster coverage is the cumulative total across all pages of the job, so
    # cost must NOT be multiplied by page count. Reproduces real job 59085:
    # 2 color pages, cov_k=11.7, price=3000, yield=20500, ref=100.
    # K cost = (11.7/100) * (3000/20500) = 0.0171  (NOT 0.0342)
    j = _job(color_pages=2, bw_pages=0, coverage_k=Decimal("11.7"))
    toner = _toner("K", price=3000, yield_pages=20500, ref_cov=Decimal("100.00"))
    result = compute_job_cost(j, toners=[toner], matched_paper=None)
    assert result["per_channel_cost"]["coverage_est_k"] == pytest.approx(0.0171, abs=0.0001)


def test_missing_actual_coverage_yields_unavailable_source_and_ignores_est():
    # coverage_est_* is the cost output slot now, not a fallback input; a
    # missing actual coverage must yield zero cost even if est holds a value.
    j = _job(coverage_k=None, coverage_est_k=Decimal("5.0"))
    toners = [_toner("K")]
    result = compute_job_cost(j, toners=toners, matched_paper=_paper())
    assert result["source"] == "unavailable"
    assert result["per_channel_cost"]["coverage_est_k"] == 0.0


def test_uses_replacement_log_when_active():
    # Cartridge installed at 2026-04-10 with price 600 (2× higher) → K cost doubles.
    log = SimpleNamespace(
        replaced_at=datetime(2026, 4, 10, tzinfo=timezone.utc),
        cartridge_price_per_unit=Decimal("600"),
        cartridge_rated_yield_pages=10000,
        cartridge_reference_coverage_pct=Decimal("5.00"),
    )
    toner = _toner("K")
    toner.replacement_logs = [log]
    j = _job()
    result = compute_job_cost(j, toners=[toner], matched_paper=_paper())
    # (5/5) * (600/10000) = 0.06
    assert result["per_channel_cost"]["coverage_est_k"] == pytest.approx(0.06, abs=0.01)


def test_paper_cost_applies_multiplier():
    p = _paper(multiplier=Decimal("1.5"))
    j = _job()
    result = compute_job_cost(j, toners=[_toner("K")], matched_paper=p)
    # 100 sheets * 0.50 * 1.5 = 75
    assert result["paper_cost"] == pytest.approx(75.00, abs=0.01)


def test_unmatched_paper_yields_zero_paper_cost():
    j = _job()
    result = compute_job_cost(j, toners=[_toner("K")], matched_paper=None)
    assert result["paper_cost"] == 0


def _toner_ch(color, channel, **kw):
    t = _toner(color, **kw)
    t.coverage_channel = channel
    return t


def test_coverage_channel_drives_cost_when_name_mismatches():
    # Real-world bug: UI stores friendly name "Black", not code "K".
    j = _job()
    toners = [_toner_ch("Black", "K")]
    result = compute_job_cost(j, toners=toners, matched_paper=_paper())
    assert result["per_channel_cost"]["coverage_est_k"] > 0


def test_coverage_channel_takes_precedence_over_name():
    j = _job()
    # name says Yellow but channel says K -> should compute the K column
    toners = [_toner_ch("Yellow", "K")]
    result = compute_job_cost(j, toners=toners, matched_paper=_paper())
    assert result["per_channel_cost"]["coverage_est_k"] > 0


def test_falls_back_to_name_when_channel_absent():
    # Legacy row with no channel but a valid code name still computes.
    j = _job()
    toners = [_toner("K")]  # no coverage_channel attribute set
    result = compute_job_cost(j, toners=toners, matched_paper=_paper())
    assert result["per_channel_cost"]["coverage_est_k"] > 0


def test_per_channel_cost_written_to_coverage_est_key():
    # coverage_k=5.0, ref=5.0 -> ratio 1.0; price 300 / yield 10000 = 0.03
    toner = _toner("K")
    toner.coverage_channel = "K"
    job = _job(coverage_k=Decimal("5.0"))
    r = compute_job_cost(job, toners=[toner], matched_paper=None)
    assert r["per_channel_cost"]["coverage_est_k"] == pytest.approx(0.03, abs=1e-4)
    assert r["toner_cost"] == pytest.approx(0.03, abs=1e-4)


def test_toner_cost_sums_only_channels_with_a_toner():
    # Only a K toner exists; C has coverage but no toner -> C contributes 0.
    toner = _toner("K")
    toner.coverage_channel = "K"
    job = _job(coverage_k=Decimal("5.0"), coverage_c=Decimal("5.0"))
    r = compute_job_cost(job, toners=[toner], matched_paper=None)
    assert "coverage_est_c" not in r["per_channel_cost"]
    assert r["toner_cost"] == pytest.approx(r["per_channel_cost"]["coverage_est_k"], abs=1e-9)


def test_empty_actual_coverage_yields_zero_and_ignores_est():
    toner = _toner("K")
    toner.coverage_channel = "K"
    # actual empty; est column holds a stale number that must NOT be used as input
    job = _job(coverage_k=None, coverage_est_k=Decimal("99.0"))
    r = compute_job_cost(job, toners=[toner], matched_paper=None)
    assert r["per_channel_cost"]["coverage_est_k"] == 0.0
    assert r["toner_cost"] == 0.0


def test_apply_cost_to_job_persists_all_columns():
    toner = _toner("K")
    toner.coverage_channel = "K"
    job = _job(coverage_k=Decimal("5.0"))
    r = compute_job_cost(job, toners=[toner], matched_paper=_paper())
    apply_cost_to_job(job, r)
    assert job.coverage_est_k == Decimal(str(r["per_channel_cost"]["coverage_est_k"]))
    assert float(job.computed_toner_cost) == pytest.approx(r["toner_cost"], abs=1e-6)
    assert float(job.computed_total_cost) == pytest.approx(r["total_cost"], abs=1e-6)
    assert job.cost_computed_at is not None
