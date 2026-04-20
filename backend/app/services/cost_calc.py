"""Cost calculation engine.

Given a PrintJob plus the printer's toners and papers, compute paper cost,
per-color toner cost, total, and metadata about which data source was used.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Iterable, Optional

# Map toner_color (normalized upper) -> (coverage_attr, coverage_est_attr, pages_attr)
# K accumulates color + bw pages; CMY use color pages only.
_COLOR_MAP: dict[str, tuple[str, str, str]] = {
    "K":     ("coverage_k",      "coverage_est_k",      "__pages_k"),
    "C":     ("coverage_c",      "coverage_est_c",      "color_pages"),
    "M":     ("coverage_m",      "coverage_est_m",      "color_pages"),
    "Y":     ("coverage_y",      "coverage_est_y",      "color_pages"),
    "GLD":   ("coverage_gld_1",  "coverage_est_gld_1",  "gold_pages"),
    "SLV":   ("coverage_slv_1",  "coverage_est_slv_1",  "silver_pages"),
    "CLR":   ("coverage_clr_1",  "coverage_est_clr_1",  "clear_pages"),
    "WHT":   ("coverage_wht_1",  "coverage_est_wht_1",  "white_pages"),
    "CR":    ("coverage_cr_1",   "coverage_est_cr_1",   "texture_pages"),
    "P":     ("coverage_p_1",    "coverage_est_p_1",    "pink_pages"),
    "PA":    ("coverage_pa_1",   "coverage_est_pa_1",   "pa_pages"),
    "GLD_6": ("coverage_gld_6",  "coverage_est_gld_6",  "gold_6_pages"),
    "SLV_6": ("coverage_slv_6",  "coverage_est_slv_6",  "silver_6_pages"),
    "WHT_6": ("coverage_wht_6",  "coverage_est_wht_6",  "white_6_pages"),
    "P_6":   ("coverage_p_6",    "coverage_est_p_6",    "pink_6_pages"),
}

# Normalize raw toner_color strings to _COLOR_MAP keys
_COLOR_ALIASES: dict[str, str] = {
    "GLD #1": "GLD", "SLV #1": "SLV", "CLR #1": "CLR", "WHT #1": "WHT",
    "CR #1": "CR", "P #1": "P", "PA #1": "PA",
    "GLD #6": "GLD_6", "SLV #6": "SLV_6", "WHT #6": "WHT_6", "P #6": "P_6",
}


def _normalize_color(raw: str) -> str:
    upper = (raw or "").strip().upper()
    return _COLOR_ALIASES.get(upper, upper.replace(" ", "_"))


def _pages_for_color(job, key: str) -> int:
    if key == "__pages_k":
        return (getattr(job, "color_pages", 0) or 0) + (getattr(job, "bw_pages", 0) or 0)
    return getattr(job, key, 0) or 0


def _active_log(toner, recorded_at):
    logs = getattr(toner, "replacement_logs", None) or []
    if not recorded_at or not logs:
        return None
    eligible = [l for l in logs if l.replaced_at and l.replaced_at <= recorded_at]
    if not eligible:
        return None
    return max(eligible, key=lambda l: l.replaced_at)


def _pricing_for_toner(toner, recorded_at):
    log = _active_log(toner, recorded_at)
    if log is not None:
        return (
            Decimal(log.cartridge_price_per_unit),
            int(log.cartridge_rated_yield_pages),
            Decimal(log.cartridge_reference_coverage_pct),
        )
    return (
        Decimal(toner.price_per_unit),
        int(toner.rated_yield_pages),
        Decimal(toner.reference_coverage_pct),
    )


def _pick_coverage(job, attr_actual: str, attr_est: str) -> tuple[Optional[Decimal], str]:
    val = getattr(job, attr_actual, None)
    if val is not None:
        try:
            d = Decimal(str(val))
            if d > 0:
                return d, "actual"
        except Exception:
            pass
    val = getattr(job, attr_est, None)
    if val is not None:
        try:
            d = Decimal(str(val))
            if d > 0:
                return d, "estimation"
        except Exception:
            pass
    return None, "unavailable"


def _dims_within(job_val, paper_val, tolerance) -> bool:
    if job_val is None or paper_val is None:
        return True
    try:
        return abs(Decimal(str(job_val)) - Decimal(str(paper_val))) <= Decimal(str(tolerance))
    except Exception:
        return True


def _gsm_within(job_gsm, paper) -> bool:
    if job_gsm is None or paper.gsm_min is None or paper.gsm_max is None:
        return True
    try:
        return int(paper.gsm_min) <= int(job_gsm) <= int(paper.gsm_max)
    except Exception:
        return True


def match_paper_for_job(job, papers: Iterable):
    """Match a print job to a Paper row using type name, dims, and gsm.

    Priority: name+dims+gsm (tier 3) > dims+gsm (tier 2) > name-only (tier 1).
    Within the same tier, pick the tightest dimensional delta.
    """
    papers = list(papers)
    if not papers:
        return None

    job_type = (getattr(job, "paper_type", "") or "").strip().lower()
    job_w = getattr(job, "paper_width_mm", None)
    job_l = getattr(job, "paper_length_mm", None)
    job_gsm = getattr(job, "paper_gsm", None)

    def score(p):
        name_hit = bool(job_type and p.name.strip().lower() == job_type)
        dims_ok = (
            _dims_within(job_w, p.width_mm, p.width_tolerance_mm)
            and _dims_within(job_l, p.length_mm, p.length_tolerance_mm)
        )
        gsm_ok = _gsm_within(job_gsm, p)
        has_dims = job_w is not None or job_l is not None
        delta = Decimal("0")
        if job_w is not None and p.width_mm is not None:
            delta += abs(Decimal(str(job_w)) - Decimal(str(p.width_mm)))
        if job_l is not None and p.length_mm is not None:
            delta += abs(Decimal(str(job_l)) - Decimal(str(p.length_mm)))
        if name_hit and dims_ok and gsm_ok:
            return (3, -delta)
        if dims_ok and gsm_ok and has_dims:
            return (2, -delta)
        if name_hit:
            return (1, Decimal("0"))
        return (0, Decimal("0"))

    scored = [(score(p), p) for p in papers]
    scored = [s for s in scored if s[0][0] > 0]
    if not scored:
        return None
    scored.sort(key=lambda s: s[0], reverse=True)
    return scored[0][1]


def compute_job_cost(job, *, toners, matched_paper) -> dict:
    """Compute paper + per-color toner cost for a single job.

    Returns dict with keys: paper_cost, toner_cost, total_cost, breakdown, source.
    Does not mutate the job object.
    """
    # Paper cost
    if matched_paper is not None:
        sheets = Decimal(str(getattr(job, "printed_sheets", 0) or 0))
        paper_cost = (
            Decimal(str(matched_paper.price_per_sheet))
            * sheets
            * Decimal(str(matched_paper.counter_multiplier))
        )
    else:
        paper_cost = Decimal("0")

    breakdown: dict[str, float] = {}
    sources: set[str] = set()
    toner_total = Decimal("0")

    recorded_at = getattr(job, "recorded_at", None)

    for t in toners:
        color_key = _normalize_color(t.toner_color)
        if color_key not in _COLOR_MAP:
            continue
        cov_attr, est_attr, pages_attr = _COLOR_MAP[color_key]
        coverage, src = _pick_coverage(job, cov_attr, est_attr)
        pages = _pages_for_color(job, pages_attr)

        sources.add(src)
        if coverage is None or pages == 0:
            breakdown[color_key.lower()] = 0.0
            continue

        price, yield_pages, ref_cov = _pricing_for_toner(t, recorded_at)
        if yield_pages == 0 or ref_cov == 0:
            breakdown[color_key.lower()] = 0.0
            continue

        price_per_page = price / Decimal(yield_pages)
        cost = (coverage / ref_cov) * price_per_page * Decimal(pages)
        toner_total += cost
        breakdown[color_key.lower()] = float(round(cost, 4))

    sources.discard("unavailable")
    if sources == {"actual"}:
        source_flag = "actual"
    elif sources == {"estimation"}:
        source_flag = "estimation"
    elif sources:
        source_flag = "mixed"
    else:
        source_flag = "unavailable"

    total = paper_cost + toner_total
    return {
        "paper_cost": float(round(paper_cost, 4)),
        "toner_cost": float(round(toner_total, 4)),
        "total_cost": float(round(total, 4)),
        "breakdown": breakdown,
        "source": source_flag,
    }
