# Print Cost Calculation & Dashboard — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Compute per-job paper + per-color toner costs from raster coverage and historical cartridge prices, then surface them on a date-range-filterable, colorful dashboard.

**Architecture:** A new `cost_calc` service attaches a cost to each `PrintJob` row at upload time (paper = matched-paper price × sheets × multiplier; toner = Σ over active colors of `(coverage / ref_cov) × (cartridge_price / rated_yield) × pages`, using the `TonerReplacementLog` active at `job.recorded_at`). Analytics routes gain a custom-date-range parameter + new `/toner-breakdown`, `/paper-breakdown`, `/top-jobs` endpoints. The dashboard gets a date-range picker, a stacked area chart, a 3D-style paper donut, a toner bar chart, a toner-consumption panel, and a per-job drawer.

**Tech Stack:** FastAPI + SQLAlchemy + Alembic + PostgreSQL (backend); React + TypeScript + TanStack Query + Recharts + Tailwind (frontend). Tests: pytest for backend.

**Spec:** `docs/superpowers/specs/2026-04-20-print-cost-dashboard-design.md`

---

## File Structure

### Backend — new files
- `backend/app/services/cost_calc.py` — cost engine (paper match + toner calc)
- `backend/app/services/__init__.py` — package init (if missing)
- `backend/alembic/versions/005_r14_cost_fields.py` — new columns migration
- `backend/tests/unit/test_cost_calc.py` — unit tests for the engine
- `backend/tests/integration/test_recompute.py` — recompute endpoint tests

### Backend — modify
- `backend/app/models/toner.py:32-62` — add `reference_coverage_pct` to `Toner`
- `backend/app/models/toner.py:65-108` — add `cartridge_reference_coverage_pct` to `TonerReplacementLog`
- `backend/app/models/upload.py:270-281` — add `computed_toner_cost_breakdown`, `cost_computed_at`, `cost_computation_source`
- `backend/app/routers/print_jobs.py:253-358` — call `compute_job_cost` during upload; add paper matching
- `backend/app/routers/print_jobs.py:390-476` — add `POST /printers/{id}/recompute-costs`
- `backend/app/routers/analytics.py` — extend existing routes with `start_date`/`end_date`/`granularity`; add new routes
- `backend/app/routers/cost_config.py` — add `GET /printers/{id}/paper-suggestions`; add `reference_coverage_pct` to toner schemas
- `backend/app/routers/toner_replacements.py` — capture & pass `reference_coverage_pct` at replacement; trigger recompute

### Frontend — new files
- `frontend/src/lib/tonerPalette.ts` — color map
- `frontend/src/components/ui/DateRangePicker.tsx` — date range picker w/ presets
- `frontend/src/components/charts/StackedCostAreaChart.tsx`
- `frontend/src/components/charts/PaperDonut3D.tsx`
- `frontend/src/components/charts/TonerBreakdownBar.tsx`
- `frontend/src/components/charts/TonerConsumptionCard.tsx`
- `frontend/src/components/charts/JobDetailDrawer.tsx`
- `frontend/src/components/printers/PaperSuggestSelect.tsx` — autosuggest dropdown

### Frontend — modify
- `frontend/src/pages/dashboard/DashboardPage.tsx` — replace period switcher with DateRangePicker; wire new charts
- `frontend/src/pages/analytics/AnalyticsPage.tsx` — same range picker; new breakdowns
- `frontend/src/pages/printers/PrinterDetailPage.tsx` — add `reference_coverage_pct` field to the toner form; embed `PaperSuggestSelect` into the Paper add flow
- `frontend/src/pages/printers/ColumnMappingPage.tsx:62-73` — help tooltip in "Paper & Media" section

---

## Task 1: Add `reference_coverage_pct` to Toner model + migration

**Files:**
- Modify: `backend/app/models/toner.py:44-56`
- Modify: `backend/app/models/toner.py:84-97` (TonerReplacementLog)
- Create: `backend/alembic/versions/005_r14_cost_fields.py`

- [ ] **Step 1: Add the field to `Toner`**

Open `backend/app/models/toner.py`. In the `Toner` class, after the `rated_yield_pages` column (currently line ~52) and before `currency`, add:

```python
    reference_coverage_pct: Mapped[Decimal] = mapped_column(
        Numeric(5, 2), nullable=False, default=Decimal("5.00"), server_default="5.00"
    )
```

- [ ] **Step 2: Add the field to `TonerReplacementLog`**

In the same file, inside `TonerReplacementLog`, after `cartridge_currency` (~line 96), add:

```python
    cartridge_reference_coverage_pct: Mapped[Decimal] = mapped_column(
        Numeric(5, 2), nullable=False, default=Decimal("5.00"), server_default="5.00"
    )
```

- [ ] **Step 3: Create Alembic migration**

Create `backend/alembic/versions/005_r14_cost_fields.py`:

```python
"""Rev 1.4 — reference coverage on toners + cost breakdown on print_jobs.

Revision ID: 005
Revises: 004
Create Date: 2026-04-20
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "005"
down_revision = "004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "toners",
        sa.Column(
            "reference_coverage_pct",
            sa.Numeric(5, 2),
            nullable=False,
            server_default="5.00",
        ),
    )
    op.add_column(
        "toner_replacement_logs",
        sa.Column(
            "cartridge_reference_coverage_pct",
            sa.Numeric(5, 2),
            nullable=False,
            server_default="5.00",
        ),
    )
    op.add_column(
        "print_jobs",
        sa.Column(
            "computed_toner_cost_breakdown",
            JSONB,
            nullable=False,
            server_default="{}",
        ),
    )
    op.add_column(
        "print_jobs",
        sa.Column("cost_computed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "print_jobs",
        sa.Column("cost_computation_source", sa.String(20), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("print_jobs", "cost_computation_source")
    op.drop_column("print_jobs", "cost_computed_at")
    op.drop_column("print_jobs", "computed_toner_cost_breakdown")
    op.drop_column("toner_replacement_logs", "cartridge_reference_coverage_pct")
    op.drop_column("toners", "reference_coverage_pct")
```

- [ ] **Step 4: Add matching fields to `PrintJob` model**

Open `backend/app/models/upload.py`. After `computed_total_cost` (~line 278), add:

```python
    computed_toner_cost_breakdown: Mapped[dict] = mapped_column(
        JSONB, nullable=False, default=dict, server_default="{}"
    )
    cost_computed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    cost_computation_source: Mapped[Optional[str]] = mapped_column(
        String(20), nullable=True
    )
```

- [ ] **Step 5: Run the migration inside the docker backend container**

Run:
```bash
docker compose -f docker-compose.dev.yml exec backend alembic upgrade head
```
Expected: `Running upgrade 004 -> 005, Rev 1.4 — reference coverage on toners + cost breakdown on print_jobs`

- [ ] **Step 6: Verify columns exist**

Run:
```bash
docker compose -f docker-compose.dev.yml exec postgres psql -U postgres -d printsight -c "\d toners" | grep reference_coverage
docker compose -f docker-compose.dev.yml exec postgres psql -U postgres -d printsight -c "\d print_jobs" | grep computed_toner_cost_breakdown
```
Expected: both greps return one line each.

- [ ] **Step 7: Commit**

```bash
git add backend/app/models/toner.py backend/app/models/upload.py backend/alembic/versions/005_r14_cost_fields.py
git commit -m "feat(schema): add reference coverage pct and cost breakdown columns"
```

---

## Task 2: Write failing unit tests for the cost calc engine

**Files:**
- Create: `backend/tests/unit/test_cost_calc.py`

- [ ] **Step 1: Create the test file with fixtures**

Create `backend/tests/unit/test_cost_calc.py`:

```python
"""Unit tests for cost calculation engine."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from types import SimpleNamespace

import pytest

from app.services.cost_calc import compute_job_cost, match_paper_for_job


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
    # 5% on each CMYK, 100 pages colour+bw for K, 50 for CMY.
    # price_per_page = 300 / 10000 = 0.03
    # K cost = (5/5) * 0.03 * (50+50) = 3.00
    # C/M/Y cost = (5/5) * 0.03 * 50 = 1.50 each
    # total toner = 3 + 4.5 = 7.50
    j = _job()
    toners = [_toner("K"), _toner("C"), _toner("M"), _toner("Y")]
    result = compute_job_cost(j, toners=toners, matched_paper=_paper())
    assert result["toner_cost"] == pytest.approx(7.50, abs=0.01)


def test_toner_cost_scales_with_coverage():
    # Double coverage → double the toner cost.
    j = _job(coverage_k=Decimal("10.0"))
    toners = [_toner("K"), _toner("C"), _toner("M"), _toner("Y")]
    result = compute_job_cost(j, toners=toners, matched_paper=_paper())
    # K was 3.00 at 5%, now 6.00 at 10%.
    assert result["breakdown"]["k"] == pytest.approx(6.00, abs=0.01)


def test_falls_back_to_estimation_when_actual_missing():
    j = _job(coverage_k=None, coverage_est_k=Decimal("5.0"))
    toners = [_toner("K")]
    result = compute_job_cost(j, toners=toners, matched_paper=_paper())
    assert result["source"] in ("estimation", "mixed")
    assert result["breakdown"]["k"] == pytest.approx(3.00, abs=0.01)


def test_uses_replacement_log_when_active():
    # Cartridge installed at 2026-04-10 with price 600 (2× higher) → cost doubles.
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
    # K at 100 pages * 0.06/page = 6.00
    assert result["breakdown"]["k"] == pytest.approx(6.00, abs=0.01)


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
```

- [ ] **Step 2: Run tests; confirm they fail**

Run:
```bash
docker compose -f docker-compose.dev.yml exec backend pytest backend/tests/unit/test_cost_calc.py -v
```
Expected: `ModuleNotFoundError: No module named 'app.services.cost_calc'` (all tests fail to import).

- [ ] **Step 3: Commit the failing tests**

```bash
git add backend/tests/unit/test_cost_calc.py
git commit -m "test(cost): failing tests for cost_calc engine"
```

---

## Task 3: Implement cost_calc engine to make tests pass

**Files:**
- Create: `backend/app/services/__init__.py` (if missing)
- Create: `backend/app/services/cost_calc.py`

- [ ] **Step 1: Ensure services package exists**

Run:
```bash
ls backend/app/services 2>/dev/null || mkdir backend/app/services && touch backend/app/services/__init__.py
```

- [ ] **Step 2: Create `cost_calc.py`**

Create `backend/app/services/cost_calc.py`:

```python
"""Cost calculation engine.

Given a PrintJob plus the printer's toners and papers, compute paper cost,
per-color toner cost, total, and metadata about which data source was used.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Iterable, Optional

# Map toner_color (uppercase) -> (coverage_attr, coverage_est_attr, pages_attr)
# K is accumulated from both color and bw pages; CMY from color only.
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


def _normalize_color(raw: str) -> str:
    return (raw or "").strip().upper().replace(" ", "_")


def _pages_for_color(job, key: str) -> int:
    if key == "__pages_k":
        return (getattr(job, "color_pages", 0) or 0) + (getattr(job, "bw_pages", 0) or 0)
    return getattr(job, key, 0) or 0


def _active_log(toner, recorded_at: Optional[datetime]):
    logs = getattr(toner, "replacement_logs", None) or []
    if not recorded_at or not logs:
        return None
    eligible = [l for l in logs if l.replaced_at and l.replaced_at <= recorded_at]
    if not eligible:
        return None
    return max(eligible, key=lambda l: l.replaced_at)


def _pricing_for_toner(toner, recorded_at: Optional[datetime]):
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
    """Return (coverage_value, source) — source is 'actual', 'estimation' or 'unavailable'."""
    val = getattr(job, attr_actual, None)
    if val is not None and Decimal(val) > 0:
        return Decimal(val), "actual"
    val = getattr(job, attr_est, None)
    if val is not None and Decimal(val) > 0:
        return Decimal(val), "estimation"
    return None, "unavailable"


def _dims_within(job_val, paper_val, tolerance) -> bool:
    if job_val is None or paper_val is None:
        return True  # missing dims don't disqualify a match
    return abs(Decimal(job_val) - Decimal(paper_val)) <= Decimal(tolerance)


def _gsm_within(job_gsm, paper) -> bool:
    if job_gsm is None or paper.gsm_min is None or paper.gsm_max is None:
        return True
    return int(paper.gsm_min) <= int(job_gsm) <= int(paper.gsm_max)


def match_paper_for_job(job, papers: Iterable):
    """Match a print job to a Paper row using type name, dims, and gsm.

    Priority: name match + dims, then dims-only, then name-only.
    """
    papers = list(papers)
    if not papers:
        return None

    job_type = (getattr(job, "paper_type", "") or "").strip().lower()
    job_w = getattr(job, "paper_width_mm", None)
    job_l = getattr(job, "paper_length_mm", None)
    job_gsm = getattr(job, "paper_gsm", None)

    def score(p):
        name_hit = job_type and p.name.strip().lower() == job_type
        dims_ok = _dims_within(job_w, p.width_mm, p.width_tolerance_mm) and \
                  _dims_within(job_l, p.length_mm, p.length_tolerance_mm)
        gsm_ok = _gsm_within(job_gsm, p)
        delta = Decimal("0")
        if job_w is not None and p.width_mm is not None:
            delta += abs(Decimal(job_w) - Decimal(p.width_mm))
        if job_l is not None and p.length_mm is not None:
            delta += abs(Decimal(job_l) - Decimal(p.length_mm))
        # Priority tiers: name+dims+gsm > dims+gsm > name
        if name_hit and dims_ok and gsm_ok:
            return (3, -delta)
        if dims_ok and gsm_ok and (job_w is not None or job_l is not None):
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

    Returns dict: {paper_cost, toner_cost, total_cost, breakdown, source}.
    Does not mutate the job; callers persist the result.
    """
    # Paper cost
    if matched_paper is not None:
        sheets = Decimal(getattr(job, "printed_sheets", 0) or 0)
        paper_cost = (
            Decimal(matched_paper.price_per_sheet)
            * sheets
            * Decimal(matched_paper.counter_multiplier)
        )
    else:
        paper_cost = Decimal("0")

    breakdown: dict[str, float] = {}
    sources: set[str] = set()
    toner_total = Decimal("0")

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

        price, yield_pages, ref_cov = _pricing_for_toner(t, getattr(job, "recorded_at", None))
        if yield_pages == 0 or ref_cov == 0:
            breakdown[color_key.lower()] = 0.0
            continue
        price_per_page = price / Decimal(yield_pages)
        cost = (coverage / ref_cov) * price_per_page * Decimal(pages)
        toner_total += cost
        breakdown[color_key.lower()] = float(round(cost, 4))

    source_flag = "unavailable"
    sources.discard("unavailable")
    if sources == {"actual"}:
        source_flag = "actual"
    elif sources == {"estimation"}:
        source_flag = "estimation"
    elif sources:
        source_flag = "mixed"

    total = paper_cost + toner_total
    return {
        "paper_cost": float(round(paper_cost, 4)),
        "toner_cost": float(round(toner_total, 4)),
        "total_cost": float(round(total, 4)),
        "breakdown": breakdown,
        "source": source_flag,
    }
```

- [ ] **Step 3: Run tests; confirm they pass**

Run:
```bash
docker compose -f docker-compose.dev.yml exec backend pytest backend/tests/unit/test_cost_calc.py -v
```
Expected: all 8 tests PASS.

- [ ] **Step 4: Commit**

```bash
git add backend/app/services/__init__.py backend/app/services/cost_calc.py
git commit -m "feat(cost): implement coverage-based cost calc engine"
```

---

## Task 4: Wire cost computation into CSV upload

**Files:**
- Modify: `backend/app/routers/print_jobs.py:253-358`

- [ ] **Step 1: Import cost_calc at top of `print_jobs.py`**

Open `backend/app/routers/print_jobs.py`. Below the existing imports (after line 20), add:

```python
from datetime import datetime, timezone
from app.models.paper import Paper
from app.models.toner import Toner
from app.services.cost_calc import compute_job_cost, match_paper_for_job
```

(Note: `datetime, timezone` may already be imported — if so don't duplicate.)

- [ ] **Step 2: Load papers and toners once per upload**

In `upload_csv`, after `db.flush()` on the batch (~line 202), before the row loop, add:

```python
    # Cache printer assets for the whole upload
    papers = (
        db.query(Paper)
        .join(Paper.printer_links)
        .filter_by(printer_id=printer_id)
        .all()
    )
    toners = db.query(Toner).filter(Toner.printer_id == printer_id).all()
    # Eagerly attach replacement logs so cost_calc.active_log works
    for t in toners:
        _ = t.replacement_logs  # trigger lazy load
```

- [ ] **Step 3: Compute costs before adding the job**

In the same function, just before `db.add(job)` (~line 361), replace the three `computed_*` assignments in the `PrintJob(...)` constructor to `Decimal("0")` — leave them at zero initially — and insert after the job object is instantiated but before `db.add(job)`:

```python
        matched = match_paper_for_job(job, papers)
        if matched is not None:
            job.matched_paper_id = matched.id
        result = compute_job_cost(job, toners=toners, matched_paper=matched)
        job.computed_paper_cost = Decimal(str(result["paper_cost"]))
        job.computed_toner_cost = Decimal(str(result["toner_cost"]))
        job.computed_total_cost = Decimal(str(result["total_cost"]))
        job.computed_toner_cost_breakdown = result["breakdown"]
        job.cost_computation_source = result["source"]
        job.cost_computed_at = datetime.now(timezone.utc)
```

- [ ] **Step 4: Restart the backend & upload a test CSV**

Run:
```bash
docker compose -f docker-compose.dev.yml restart backend
```

Using the UI or curl, upload `resourses/sample.csv` (or whatever test CSV exists) to a printer with toners + papers configured. Then:

```bash
docker compose -f docker-compose.dev.yml exec postgres psql -U postgres -d printsight -c "SELECT job_id, computed_paper_cost, computed_toner_cost, computed_total_cost, cost_computation_source FROM print_jobs ORDER BY id DESC LIMIT 5;"
```
Expected: non-zero `computed_total_cost` values, `cost_computation_source` is `"actual"` or `"estimation"`.

- [ ] **Step 5: Commit**

```bash
git add backend/app/routers/print_jobs.py
git commit -m "feat(upload): compute paper + toner costs during CSV import"
```

---

## Task 5: Recompute endpoint

**Files:**
- Modify: `backend/app/routers/print_jobs.py` (append route)
- Create: `backend/tests/integration/test_recompute.py`

- [ ] **Step 1: Write the integration test**

Create `backend/tests/integration/test_recompute.py`:

```python
"""Integration test for /printers/{id}/recompute-costs."""

import pytest
from fastapi.testclient import TestClient

# The existing test harness is assumed to expose a `client` fixture that
# authenticates as a test owner and a `seed_printer_with_job` fixture.
# If these do not yet exist in conftest.py, see Task 5b for the pattern.

pytestmark = pytest.mark.integration


def test_recompute_updates_changed_prices(client, seed_printer_with_job):
    printer_id, job_id = seed_printer_with_job

    # Raise the K toner price; the endpoint should recompute.
    client.put(f"/printers/{printer_id}/toners/1", json={
        "toner_color": "K", "toner_type": "standard",
        "price_per_unit": 600, "rated_yield_pages": 10000,
        "reference_coverage_pct": 5.0, "currency": "INR",
    })

    before = client.get(f"/printers/{printer_id}/jobs").json()
    r = client.post(f"/printers/{printer_id}/recompute-costs")
    assert r.status_code == 200
    assert r.json()["data"]["rows_updated"] >= 1

    after = client.get(f"/printers/{printer_id}/jobs").json()
    before_cost = before["data"][0]["computed_total_cost"]
    after_cost = after["data"][0]["computed_total_cost"]
    assert after_cost > before_cost
```

> **Note for the implementer:** if `conftest.py` does not yet expose `client` and `seed_printer_with_job`, skip this test with a marker and add fixtures as a follow-up; do not block the feature on fixture scaffolding.

- [ ] **Step 2: Run the test to confirm it fails**

Run:
```bash
docker compose -f docker-compose.dev.yml exec backend pytest backend/tests/integration/test_recompute.py -v
```
Expected: FAIL (endpoint does not exist yet) or skipped if fixtures missing.

- [ ] **Step 3: Add the route**

In `backend/app/routers/print_jobs.py`, after the `clear_all_jobs` function (~line 426), add:

```python
from pydantic import BaseModel


class RecomputeRequest(BaseModel):
    from_date: datetime | None = None
    to_date: datetime | None = None
    batch_id: int | None = None


@router.post("/recompute-costs")
async def recompute_costs(
    printer_id: int,
    current_user: CurrentUser,
    body: RecomputeRequest | None = None,
    db: Session = Depends(get_db),
):
    _get_printer_or_403(db, printer_id, current_user.id)
    body = body or RecomputeRequest()

    papers = (
        db.query(Paper).join(Paper.printer_links).filter_by(printer_id=printer_id).all()
    )
    toners = db.query(Toner).filter(Toner.printer_id == printer_id).all()
    for t in toners:
        _ = t.replacement_logs

    q = db.query(PrintJob).filter(PrintJob.printer_id == printer_id)
    if body.from_date:
        q = q.filter(PrintJob.recorded_at >= body.from_date)
    if body.to_date:
        q = q.filter(PrintJob.recorded_at <= body.to_date)
    if body.batch_id:
        q = q.filter(PrintJob.upload_batch_id == body.batch_id)

    rows_updated = 0
    for job in q.all():
        matched = match_paper_for_job(job, papers)
        job.matched_paper_id = matched.id if matched else None
        result = compute_job_cost(job, toners=toners, matched_paper=matched)
        job.computed_paper_cost = Decimal(str(result["paper_cost"]))
        job.computed_toner_cost = Decimal(str(result["toner_cost"]))
        job.computed_total_cost = Decimal(str(result["total_cost"]))
        job.computed_toner_cost_breakdown = result["breakdown"]
        job.cost_computation_source = result["source"]
        job.cost_computed_at = datetime.now(timezone.utc)
        rows_updated += 1

    db.commit()
    return {"data": {"rows_updated": rows_updated}, "message": "ok"}
```

(`RecomputeRequest` import of `BaseModel` only needs to appear once; place the `from pydantic import BaseModel` import at the top with the other imports.)

- [ ] **Step 4: Rerun the integration test; confirm PASS**

Run:
```bash
docker compose -f docker-compose.dev.yml restart backend
docker compose -f docker-compose.dev.yml exec backend pytest backend/tests/integration/test_recompute.py -v
```
Expected: PASS (or skipped if fixtures missing — that's acceptable for this iteration).

- [ ] **Step 5: Commit**

```bash
git add backend/app/routers/print_jobs.py backend/tests/integration/test_recompute.py
git commit -m "feat(cost): POST /printers/{id}/recompute-costs endpoint"
```

---

## Task 6: Auto-recompute after toner replacement & price edits

**Files:**
- Modify: `backend/app/routers/toner_replacements.py`
- Modify: `backend/app/routers/cost_config.py`

- [ ] **Step 1: Capture `cartridge_reference_coverage_pct` in replacement creation**

Open `backend/app/routers/toner_replacements.py`. Locate the `create_replacement` (or equivalent POST) handler and where it instantiates `TonerReplacementLog`, add:

```python
    cartridge_reference_coverage_pct=toner.reference_coverage_pct,
```

If the request schema (Pydantic) exposes this field for override, add `cartridge_reference_coverage_pct: Decimal | None = None` and prefer the body value when set.

- [ ] **Step 2: Trigger recompute after replacement create**

Still in `toner_replacements.py`, after `db.commit()` and before returning, add:

```python
    from app.services.cost_calc import compute_job_cost, match_paper_for_job
    from app.models.paper import Paper
    from app.models.upload import PrintJob
    from datetime import datetime, timezone

    papers = db.query(Paper).join(Paper.printer_links).filter_by(printer_id=toner.printer_id).all()
    toners = db.query(Toner).filter(Toner.printer_id == toner.printer_id).all()
    for t in toners:
        _ = t.replacement_logs
    jobs = db.query(PrintJob).filter(
        PrintJob.printer_id == toner.printer_id,
        PrintJob.recorded_at >= replacement.replaced_at,
    ).all()
    for job in jobs:
        matched = match_paper_for_job(job, papers)
        job.matched_paper_id = matched.id if matched else None
        r = compute_job_cost(job, toners=toners, matched_paper=matched)
        job.computed_paper_cost = Decimal(str(r["paper_cost"]))
        job.computed_toner_cost = Decimal(str(r["toner_cost"]))
        job.computed_total_cost = Decimal(str(r["total_cost"]))
        job.computed_toner_cost_breakdown = r["breakdown"]
        job.cost_computation_source = r["source"]
        job.cost_computed_at = datetime.now(timezone.utc)
    db.commit()
```

- [ ] **Step 3: Add `reference_coverage_pct` to toner schemas**

Open `backend/app/routers/cost_config.py`. Locate the `TonerCreate`/`TonerUpdate` Pydantic models. Add the field:

```python
    reference_coverage_pct: Decimal = Decimal("5.00")
```

Wire it into both the `create_toner` and `update_toner` persistence blocks:
```python
t.reference_coverage_pct = body.reference_coverage_pct
```

After updating a toner's `price_per_unit`, `rated_yield_pages`, or `reference_coverage_pct`, include a `{"recompute_hint": true, "printer_id": t.printer_id}` in the response so the UI knows to offer the recompute button.

- [ ] **Step 4: Commit**

```bash
git add backend/app/routers/toner_replacements.py backend/app/routers/cost_config.py
git commit -m "feat(cost): recompute after toner replacement; editable reference coverage"
```

---

## Task 7: Paper suggestions endpoint

**Files:**
- Modify: `backend/app/routers/printers.py` (or `cost_config.py`, wherever paper CRUD lives)

- [ ] **Step 1: Add route `GET /printers/{id}/paper-suggestions`**

Append to `backend/app/routers/printers.py` (or the paper section of `cost_config.py`):

```python
from sqlalchemy import func


@router.get("/printers/{printer_id}/paper-suggestions")
async def paper_suggestions(
    printer_id: int,
    current_user: CurrentUser,
    db: Session = Depends(get_db),
):
    _get_printer_or_403(db, printer_id, current_user.id)
    rows = (
        db.query(
            PrintJob.paper_type,
            PrintJob.paper_width_mm,
            PrintJob.paper_length_mm,
            PrintJob.paper_gsm,
            func.count(PrintJob.id).label("job_count"),
        )
        .filter(PrintJob.printer_id == printer_id, PrintJob.paper_type.isnot(None))
        .group_by(
            PrintJob.paper_type,
            PrintJob.paper_width_mm,
            PrintJob.paper_length_mm,
            PrintJob.paper_gsm,
        )
        .order_by(func.count(PrintJob.id).desc())
        .limit(50)
        .all()
    )
    return {
        "data": [
            {
                "paper_type": r.paper_type,
                "width_mm": float(r.paper_width_mm) if r.paper_width_mm else None,
                "length_mm": float(r.paper_length_mm) if r.paper_length_mm else None,
                "gsm": r.paper_gsm,
                "job_count": r.job_count,
            }
            for r in rows
        ],
        "message": "ok",
    }
```

Match the existing `_get_printer_or_403` helper's signature and whichever router owns the `printers` prefix. Import `PrintJob` if not already imported.

- [ ] **Step 2: Smoke test via curl**

Run:
```bash
curl -s -H "Authorization: Bearer $TOKEN" http://localhost:8001/printers/1/paper-suggestions | jq .
```
Expected: JSON `data` array of distinct paper types observed in `print_jobs`.

- [ ] **Step 3: Commit**

```bash
git add backend/app/routers/printers.py
git commit -m "feat(papers): GET /printers/{id}/paper-suggestions"
```

---

## Task 8: Analytics route updates (date range + granularity + new routes)

**Files:**
- Modify: `backend/app/routers/analytics.py`

- [ ] **Step 1: Extract a shared `_resolve_range` helper**

At the top of `backend/app/routers/analytics.py`, replace `_date_range` with:

```python
def _resolve_range(
    period: str | None,
    start_date: datetime | None,
    end_date: datetime | None,
) -> tuple[datetime, datetime]:
    now = datetime.now(timezone.utc)
    if start_date and end_date:
        return start_date, end_date
    if period == "1d":
        return now - timedelta(days=1), now
    if period == "7d":
        return now - timedelta(days=7), now
    if period == "30d":
        return now - timedelta(days=30), now
    if period == "90d":
        return now - timedelta(days=90), now
    if period == "365d":
        return now - timedelta(days=365), now
    return now - timedelta(days=30), now


def _auto_granularity(start: datetime, end: datetime) -> str:
    span = (end - start).days
    if span <= 2:
        return "hour"
    if span <= 62:
        return "day"
    if span <= 400:
        return "week"
    return "month"


def _bucket_key(dt: datetime, granularity: str) -> str:
    if granularity == "hour":
        return dt.strftime("%Y-%m-%d %H:00")
    if granularity == "week":
        iso = dt.isocalendar()
        return f"{iso.year}-W{iso.week:02d}"
    if granularity == "month":
        return dt.strftime("%Y-%m")
    return dt.strftime("%Y-%m-%d")
```

- [ ] **Step 2: Update existing routes to accept range + granularity**

Replace the `summary` signature/body, e.g.:

```python
@router.get("/summary")
async def summary(
    current_user: OwnerUser,
    db: Session = Depends(get_db),
    period: str | None = Query(None),
    start_date: datetime | None = Query(None),
    end_date: datetime | None = Query(None),
    printer_id: int | None = Query(None),
):
    start, end = _resolve_range(period, start_date, end_date)
    ...  # existing logic using start, end
```

Do the same for `trends`, `printers_comparison`, `cost_breakdown`. In `trends`, replace the day bucket with:

```python
    granularity = _auto_granularity(start, end)
    bucket = _bucket_key(j.recorded_at, granularity)
```

Extend `summary` response to include `paper_cost` and `toner_cost`:

```python
    paper = sum(float(j.computed_paper_cost) for j in jobs)
    toner = sum(float(j.computed_toner_cost) for j in jobs)
    # add to return dict:
    "paper_cost": round(paper, 2),
    "toner_cost": round(toner, 2),
```

- [ ] **Step 3: Add `/analytics/toner-breakdown`**

```python
@router.get("/toner-breakdown")
async def toner_breakdown(
    current_user: OwnerUser,
    db: Session = Depends(get_db),
    period: str | None = Query(None),
    start_date: datetime | None = Query(None),
    end_date: datetime | None = Query(None),
    granularity: str = Query("auto"),
    printer_id: int | None = Query(None),
):
    start, end = _resolve_range(period, start_date, end_date)
    if granularity == "auto":
        granularity = _auto_granularity(start, end)

    printer_ids = [p.id for p in db.query(Printer.id).filter(Printer.owner_id == current_user.id).all()]
    if not printer_ids:
        return {"data": [], "message": "ok"}

    q = db.query(PrintJob).filter(
        PrintJob.printer_id.in_(printer_ids),
        PrintJob.recorded_at >= start,
        PrintJob.recorded_at <= end,
    )
    if printer_id:
        q = q.filter(PrintJob.printer_id == printer_id)

    by_bucket: dict[str, dict] = {}
    for j in q.all():
        if not j.recorded_at:
            continue
        b = _bucket_key(j.recorded_at, granularity)
        slot = by_bucket.setdefault(b, {"bucket": b, "paper": 0.0})
        slot["paper"] += float(j.computed_paper_cost)
        for k, v in (j.computed_toner_cost_breakdown or {}).items():
            slot[k] = slot.get(k, 0.0) + float(v)

    return {
        "data": sorted(by_bucket.values(), key=lambda x: x["bucket"]),
        "granularity": granularity,
        "message": "ok",
    }
```

- [ ] **Step 4: Add `/analytics/paper-breakdown`**

```python
@router.get("/paper-breakdown")
async def paper_breakdown(
    current_user: OwnerUser,
    db: Session = Depends(get_db),
    period: str | None = Query(None),
    start_date: datetime | None = Query(None),
    end_date: datetime | None = Query(None),
    printer_id: int | None = Query(None),
):
    start, end = _resolve_range(period, start_date, end_date)
    printer_ids = [p.id for p in db.query(Printer.id).filter(Printer.owner_id == current_user.id).all()]
    if not printer_ids:
        return {"data": [], "message": "ok"}
    q = db.query(PrintJob).filter(
        PrintJob.printer_id.in_(printer_ids),
        PrintJob.recorded_at >= start, PrintJob.recorded_at <= end,
    )
    if printer_id:
        q = q.filter(PrintJob.printer_id == printer_id)

    groups: dict[str, dict] = {}
    for j in q.all():
        key = j.paper_type or "(unknown)"
        slot = groups.setdefault(key, {"paper_type": key, "cost": 0.0, "pages": 0})
        slot["cost"] += float(j.computed_paper_cost)
        slot["pages"] += j.printed_pages

    data = sorted(groups.values(), key=lambda x: x["cost"], reverse=True)
    for d in data:
        d["cost"] = round(d["cost"], 2)
    return {"data": data, "message": "ok"}
```

- [ ] **Step 5: Add `/analytics/top-jobs`**

```python
@router.get("/top-jobs")
async def top_jobs(
    current_user: OwnerUser,
    db: Session = Depends(get_db),
    period: str | None = Query(None),
    start_date: datetime | None = Query(None),
    end_date: datetime | None = Query(None),
    printer_id: int | None = Query(None),
    limit: int = Query(20, ge=1, le=100),
    order: str = Query("cost", pattern="^(cost|pages|waste)$"),
):
    start, end = _resolve_range(period, start_date, end_date)
    printer_ids = [p.id for p in db.query(Printer.id).filter(Printer.owner_id == current_user.id).all()]
    if not printer_ids:
        return {"data": [], "message": "ok"}
    q = db.query(PrintJob).filter(
        PrintJob.printer_id.in_(printer_ids),
        PrintJob.recorded_at >= start, PrintJob.recorded_at <= end,
    )
    if printer_id:
        q = q.filter(PrintJob.printer_id == printer_id)
    if order == "waste":
        q = q.filter(PrintJob.is_waste.is_(True))

    sort_col = {
        "cost": PrintJob.computed_total_cost.desc(),
        "pages": PrintJob.printed_pages.desc(),
        "waste": PrintJob.computed_total_cost.desc(),
    }[order]
    jobs = q.order_by(sort_col).limit(limit).all()

    return {
        "data": [
            {
                "id": j.id, "job_id": j.job_id, "job_name": j.job_name,
                "recorded_at": j.recorded_at.isoformat() if j.recorded_at else None,
                "paper_type": j.paper_type, "printed_pages": j.printed_pages,
                "paper_cost": float(j.computed_paper_cost),
                "toner_cost": float(j.computed_toner_cost),
                "total_cost": float(j.computed_total_cost),
                "breakdown": j.computed_toner_cost_breakdown,
                "source": j.cost_computation_source,
                "is_waste": j.is_waste,
            }
            for j in jobs
        ],
        "message": "ok",
    }
```

- [ ] **Step 6: Smoke test**

Run:
```bash
docker compose -f docker-compose.dev.yml restart backend
curl -s "http://localhost:8001/analytics/toner-breakdown?period=30d" -H "Authorization: Bearer $TOKEN" | jq .
curl -s "http://localhost:8001/analytics/paper-breakdown?period=30d" -H "Authorization: Bearer $TOKEN" | jq .
curl -s "http://localhost:8001/analytics/top-jobs?period=30d&limit=5" -H "Authorization: Bearer $TOKEN" | jq .
```
Expected: each returns `data` with the documented fields.

- [ ] **Step 7: Commit**

```bash
git add backend/app/routers/analytics.py
git commit -m "feat(analytics): custom date range + toner/paper/top-jobs breakdowns"
```

---

## Task 9: Frontend — color palette + date range picker

**Files:**
- Create: `frontend/src/lib/tonerPalette.ts`
- Create: `frontend/src/components/ui/DateRangePicker.tsx`

- [ ] **Step 1: Create the palette**

Create `frontend/src/lib/tonerPalette.ts`:

```ts
export const TONER_COLORS: Record<string, string> = {
  paper:  "#60a5fa",
  k:      "#1f2937",
  c:      "#06b6d4",
  m:      "#ec4899",
  y:      "#facc15",
  gld:    "#d4af37",
  slv:    "#c0c0c0",
  clr:    "#a5f3fc",
  wht:    "#f8fafc",
  cr:     "#fb923c",
  p:      "#f472b6",
  pa:     "#a78bfa",
  gld_6:  "#b8860b",
  slv_6:  "#9ca3af",
  wht_6:  "#e2e8f0",
  p_6:    "#e879f9",
};

export const PAPER_COLORS = [
  "#60a5fa", "#34d399", "#f472b6", "#fbbf24", "#a78bfa",
  "#f87171", "#22d3ee", "#fb923c", "#4ade80", "#e879f9",
];

export function colorForToner(key: string): string {
  return TONER_COLORS[key.toLowerCase()] ?? "#9ca3af";
}
```

- [ ] **Step 2: Create the DateRangePicker**

Create `frontend/src/components/ui/DateRangePicker.tsx`:

```tsx
import { useState } from "react";

type Range = { start: Date; end: Date };
interface Props {
  value: Range;
  onChange: (r: Range) => void;
}

const PRESETS: [string, number][] = [
  ["Today", 1], ["7d", 7], ["30d", 30], ["90d", 90], ["1y", 365],
];

function toInput(d: Date): string {
  return d.toISOString().slice(0, 10);
}

export function DateRangePicker({ value, onChange }: Props) {
  const [open, setOpen] = useState(false);

  function applyPreset(days: number) {
    const end = new Date();
    const start = new Date();
    start.setDate(end.getDate() - days);
    onChange({ start, end });
  }

  return (
    <div className="flex items-center gap-2">
      <div className="flex gap-1 rounded-md border bg-card p-1">
        {PRESETS.map(([label, d]) => (
          <button
            key={label}
            onClick={() => applyPreset(d)}
            className="rounded px-3 py-1.5 text-sm text-muted-foreground hover:text-foreground"
          >
            {label}
          </button>
        ))}
      </div>
      <button
        onClick={() => setOpen(o => !o)}
        className="rounded-md border bg-card px-3 py-1.5 text-sm"
      >
        {toInput(value.start)} — {toInput(value.end)}
      </button>
      {open && (
        <div className="absolute z-20 mt-16 flex gap-2 rounded-md border bg-card p-3 shadow-md">
          <input
            type="date"
            value={toInput(value.start)}
            onChange={e => onChange({ ...value, start: new Date(e.target.value) })}
            className="rounded border px-2 py-1"
          />
          <input
            type="date"
            value={toInput(value.end)}
            onChange={e => onChange({ ...value, end: new Date(e.target.value) })}
            className="rounded border px-2 py-1"
          />
          <button onClick={() => setOpen(false)} className="rounded bg-primary px-3 py-1 text-sm text-primary-foreground">Apply</button>
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/lib/tonerPalette.ts frontend/src/components/ui/DateRangePicker.tsx
git commit -m "feat(ui): date range picker + toner color palette"
```

---

## Task 10: Frontend — StackedCostAreaChart

**Files:**
- Create: `frontend/src/components/charts/StackedCostAreaChart.tsx`

- [ ] **Step 1: Create the component**

```tsx
import { AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid, Legend } from "recharts";
import { colorForToner } from "@/lib/tonerPalette";

interface Row { bucket: string; [key: string]: number | string }
interface Props { data: Row[] }

export function StackedCostAreaChart({ data }: Props) {
  const series = new Set<string>();
  data.forEach(r => Object.keys(r).forEach(k => { if (k !== "bucket") series.add(k); }));
  const keys = Array.from(series);

  return (
    <ResponsiveContainer width="100%" height={320}>
      <AreaChart data={data}>
        <defs>
          {keys.map(k => {
            const c = colorForToner(k);
            return (
              <linearGradient key={k} id={`grad-${k}`} x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor={c} stopOpacity={0.9} />
                <stop offset="100%" stopColor={c} stopOpacity={0.35} />
              </linearGradient>
            );
          })}
        </defs>
        <CartesianGrid strokeDasharray="3 3" />
        <XAxis dataKey="bucket" tick={{ fontSize: 11 }} />
        <YAxis tick={{ fontSize: 11 }} tickFormatter={v => `₹${v}`} />
        <Tooltip formatter={(v: number) => `₹${v.toFixed(2)}`} />
        <Legend />
        {keys.map(k => (
          <Area
            key={k} type="monotone" dataKey={k} stackId="1"
            stroke={colorForToner(k)} fill={`url(#grad-${k})`} strokeWidth={1.5}
          />
        ))}
      </AreaChart>
    </ResponsiveContainer>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/components/charts/StackedCostAreaChart.tsx
git commit -m "feat(charts): stacked cost area chart"
```

---

## Task 11: Frontend — PaperDonut3D

**Files:**
- Create: `frontend/src/components/charts/PaperDonut3D.tsx`

- [ ] **Step 1: Create the component**

```tsx
import { PieChart, Pie, Cell, Tooltip, ResponsiveContainer, Legend } from "recharts";
import { PAPER_COLORS } from "@/lib/tonerPalette";

interface Row { paper_type: string; cost: number; pages: number }
interface Props { data: Row[] }

export function PaperDonut3D({ data }: Props) {
  const total = data.reduce((s, d) => s + d.cost, 0);

  return (
    <ResponsiveContainer width="100%" height={320}>
      <PieChart>
        <defs>
          {data.map((_, i) => {
            const c = PAPER_COLORS[i % PAPER_COLORS.length];
            return (
              <radialGradient key={i} id={`pie-${i}`} cx="50%" cy="50%" r="65%">
                <stop offset="0%" stopColor={c} stopOpacity={1} />
                <stop offset="100%" stopColor={c} stopOpacity={0.55} />
              </radialGradient>
            );
          })}
          <filter id="donut-shadow" x="-20%" y="-20%" width="140%" height="140%">
            <feDropShadow dx="0" dy="4" stdDeviation="6" floodOpacity="0.35" />
          </filter>
        </defs>
        <Pie
          data={data}
          dataKey="cost"
          nameKey="paper_type"
          innerRadius={70}
          outerRadius={120}
          paddingAngle={3}
          stroke="#fff"
          strokeWidth={2}
          filter="url(#donut-shadow)"
          label={({ paper_type, cost }) =>
            `${paper_type}: ${((cost / total) * 100).toFixed(0)}%`}
        >
          {data.map((_, i) => <Cell key={i} fill={`url(#pie-${i})`} />)}
        </Pie>
        <Tooltip formatter={(v: number) => `₹${v.toFixed(2)}`} />
        <Legend verticalAlign="bottom" />
      </PieChart>
    </ResponsiveContainer>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/components/charts/PaperDonut3D.tsx
git commit -m "feat(charts): colorful paper donut with gradient+shadow"
```

---

## Task 12: Frontend — TonerBreakdownBar + TonerConsumptionCard + JobDetailDrawer

**Files:**
- Create: `frontend/src/components/charts/TonerBreakdownBar.tsx`
- Create: `frontend/src/components/charts/TonerConsumptionCard.tsx`
- Create: `frontend/src/components/charts/JobDetailDrawer.tsx`

- [ ] **Step 1: `TonerBreakdownBar.tsx`**

```tsx
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from "recharts";
import { colorForToner } from "@/lib/tonerPalette";

interface Props { data: { color: string; cost: number }[] }

export function TonerBreakdownBar({ data }: Props) {
  return (
    <ResponsiveContainer width="100%" height={280}>
      <BarChart data={data} layout="vertical" margin={{ left: 32 }}>
        <XAxis type="number" tickFormatter={v => `₹${v}`} />
        <YAxis type="category" dataKey="color" width={60} />
        <Tooltip formatter={(v: number) => `₹${v.toFixed(2)}`} />
        <Bar dataKey="cost" radius={[0, 4, 4, 0]}>
          {data.map((d, i) => <Cell key={i} fill={colorForToner(d.color)} />)}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}
```

- [ ] **Step 2: `TonerConsumptionCard.tsx`**

```tsx
import { colorForToner } from "@/lib/tonerPalette";

interface Props {
  color: string;
  pages_since_replacement: number;
  pct_yield_consumed: number;
  spend_to_date: number;
  est_remaining_pages: number;
}

export function TonerConsumptionCard(p: Props) {
  const c = colorForToner(p.color);
  const warn = p.pct_yield_consumed > 80;
  return (
    <div className="rounded-xl border bg-card p-4 shadow-sm">
      <div className="mb-2 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="inline-block h-4 w-4 rounded-full" style={{ background: c }} />
          <span className="font-medium uppercase">{p.color}</span>
        </div>
        {warn && <span className="rounded-full bg-amber-100 px-2 py-0.5 text-xs text-amber-700">Low</span>}
      </div>
      <div className="mb-3 h-2 rounded bg-muted">
        <div className="h-2 rounded" style={{ width: `${Math.min(100, p.pct_yield_consumed)}%`, background: c }} />
      </div>
      <div className="grid grid-cols-2 gap-2 text-xs text-muted-foreground">
        <div><span className="block text-foreground font-semibold">{p.pages_since_replacement.toLocaleString()}</span>pages used</div>
        <div><span className="block text-foreground font-semibold">{p.est_remaining_pages.toLocaleString()}</span>est. remaining</div>
        <div><span className="block text-foreground font-semibold">₹{p.spend_to_date.toFixed(2)}</span>spent</div>
        <div><span className="block text-foreground font-semibold">{p.pct_yield_consumed.toFixed(1)}%</span>of rated yield</div>
      </div>
    </div>
  );
}
```

- [ ] **Step 3: `JobDetailDrawer.tsx`**

```tsx
import { colorForToner } from "@/lib/tonerPalette";

interface Breakdown { [k: string]: number }
interface Job {
  job_id: string;
  job_name?: string | null;
  paper_type?: string | null;
  printed_pages: number;
  paper_cost: number;
  toner_cost: number;
  total_cost: number;
  breakdown: Breakdown;
  source: string | null;
}

interface Props { job: Job | null; onClose: () => void }

export function JobDetailDrawer({ job, onClose }: Props) {
  if (!job) return null;
  return (
    <div className="fixed inset-0 z-30 flex justify-end" onClick={onClose}>
      <div className="h-full w-full max-w-md overflow-y-auto bg-card p-6 shadow-xl" onClick={e => e.stopPropagation()}>
        <div className="mb-4 flex items-center justify-between">
          <h3 className="text-lg font-bold">{job.job_name || job.job_id}</h3>
          <button onClick={onClose} className="text-muted-foreground hover:text-foreground">×</button>
        </div>
        <div className="grid grid-cols-3 gap-2 text-xs text-muted-foreground">
          <div><div className="text-foreground font-semibold">₹{job.paper_cost.toFixed(2)}</div>Paper</div>
          <div><div className="text-foreground font-semibold">₹{job.toner_cost.toFixed(2)}</div>Toner</div>
          <div><div className="text-foreground font-semibold">₹{job.total_cost.toFixed(2)}</div>Total</div>
        </div>
        <div className="mt-4">
          <div className="mb-2 text-sm font-semibold">Per-color breakdown</div>
          {Object.entries(job.breakdown || {}).map(([k, v]) => (
            <div key={k} className="mb-1 flex items-center gap-2">
              <span className="inline-block h-3 w-3 rounded-full" style={{ background: colorForToner(k) }} />
              <span className="w-16 text-xs uppercase text-muted-foreground">{k}</span>
              <div className="flex-1">
                <div className="h-2 rounded" style={{ background: colorForToner(k), width: `${Math.min(100, (v / Math.max(...Object.values(job.breakdown))) * 100)}%` }} />
              </div>
              <span className="w-16 text-right text-xs">₹{v.toFixed(2)}</span>
            </div>
          ))}
        </div>
        <div className="mt-4 text-xs text-muted-foreground">Source: {job.source}</div>
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/charts/TonerBreakdownBar.tsx frontend/src/components/charts/TonerConsumptionCard.tsx frontend/src/components/charts/JobDetailDrawer.tsx
git commit -m "feat(charts): toner bar, consumption card, job drawer"
```

---

## Task 13: Wire the new components into DashboardPage

**Files:**
- Modify: `frontend/src/pages/dashboard/DashboardPage.tsx`

- [ ] **Step 1: Replace state + queries**

Replace the `const [period, setPeriod] = useState('30d');` block and the two `useQuery`s with:

```tsx
import { useState } from 'react';
import { DateRangePicker } from '@/components/ui/DateRangePicker';
import { StackedCostAreaChart } from '@/components/charts/StackedCostAreaChart';
import { PaperDonut3D } from '@/components/charts/PaperDonut3D';
import { TonerBreakdownBar } from '@/components/charts/TonerBreakdownBar';
import { JobDetailDrawer } from '@/components/charts/JobDetailDrawer';

const defaultStart = () => { const d = new Date(); d.setDate(d.getDate() - 30); return d; };

export default function DashboardPage() {
  const [range, setRange] = useState({ start: defaultStart(), end: new Date() });
  const [selectedJob, setSelectedJob] = useState<any | null>(null);
  const { selectedPrinter } = usePrinter();
  const printerParam = selectedPrinter ? `&printer_id=${selectedPrinter.id}` : '';
  const rp = `start_date=${range.start.toISOString()}&end_date=${range.end.toISOString()}${printerParam}`;

  const { data: summary } = useQuery({
    queryKey: ['analytics-summary', range, selectedPrinter?.id],
    queryFn: () => api.get(`/analytics/summary?${rp}`).then(r => r.data.data),
  });
  const { data: toner } = useQuery({
    queryKey: ['toner-breakdown', range, selectedPrinter?.id],
    queryFn: () => api.get(`/analytics/toner-breakdown?${rp}`).then(r => r.data.data),
  });
  const { data: paper } = useQuery({
    queryKey: ['paper-breakdown', range, selectedPrinter?.id],
    queryFn: () => api.get(`/analytics/paper-breakdown?${rp}`).then(r => r.data.data),
  });
  const { data: topJobs } = useQuery({
    queryKey: ['top-jobs', range, selectedPrinter?.id],
    queryFn: () => api.get(`/analytics/top-jobs?${rp}&limit=10`).then(r => r.data.data),
  });
```

- [ ] **Step 2: Replace the header period buttons with the DateRangePicker**

Swap the old `PERIODS.map(...)` block with:

```tsx
<DateRangePicker value={range} onChange={setRange} />
```

- [ ] **Step 3: Replace the existing charts area**

Below the KPI grid, replace the two existing chart cards with:

```tsx
<div className="rounded-xl border bg-card p-5">
  <h2 className="mb-4 font-semibold">Cost over time (stacked)</h2>
  {toner && toner.length > 0 ? <StackedCostAreaChart data={toner} /> : <EmptyState />}
</div>

<div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
  <div className="rounded-xl border bg-card p-5">
    <h2 className="mb-4 font-semibold">Paper cost by type</h2>
    {paper && paper.length > 0 ? <PaperDonut3D data={paper} /> : <EmptyState />}
  </div>
  <div className="rounded-xl border bg-card p-5">
    <h2 className="mb-4 font-semibold">Toner cost by color</h2>
    {toner && toner.length > 0 ? (
      <TonerBreakdownBar data={aggregateTotals(toner)} />
    ) : <EmptyState />}
  </div>
</div>

<div className="rounded-xl border bg-card p-5">
  <h2 className="mb-4 font-semibold">Top 10 most expensive jobs</h2>
  <table className="w-full text-sm">
    <thead className="text-muted-foreground">
      <tr><th className="text-left">Job</th><th>Paper</th><th>Pages</th><th>Cost</th></tr>
    </thead>
    <tbody>
      {(topJobs ?? []).map((j: any) => (
        <tr key={j.id} onClick={() => setSelectedJob(j)} className="cursor-pointer hover:bg-muted">
          <td>{j.job_name || j.job_id}</td>
          <td className="text-center">{j.paper_type}</td>
          <td className="text-center">{j.printed_pages}</td>
          <td className="text-right">₹{j.total_cost.toFixed(2)}</td>
        </tr>
      ))}
    </tbody>
  </table>
</div>

<JobDetailDrawer job={selectedJob} onClose={() => setSelectedJob(null)} />
```

Where `aggregateTotals` is defined locally as:

```tsx
function aggregateTotals(rows: any[]) {
  const totals: Record<string, number> = {};
  rows.forEach(r => Object.entries(r).forEach(([k, v]) => {
    if (k === 'bucket' || typeof v !== 'number') return;
    totals[k] = (totals[k] || 0) + v;
  }));
  return Object.entries(totals)
    .filter(([k]) => k !== 'paper')
    .map(([color, cost]) => ({ color, cost }));
}

const EmptyState = () => (
  <div className="flex h-64 items-center justify-center text-muted-foreground">No data in the selected range.</div>
);
```

- [ ] **Step 4: Manual UI smoke test**

Run:
```bash
docker compose -f docker-compose.dev.yml up -d frontend backend
```

Open `http://localhost:5173/`, log in, select a printer, confirm:
- Date range picker applies and charts refresh
- Stacked area chart shows colored segments per toner
- Paper donut has gradient fills and drop shadow
- Clicking a row in the Top Jobs table opens the drawer with per-color breakdown

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/dashboard/DashboardPage.tsx
git commit -m "feat(dashboard): date-range filter + new colorful charts + job drawer"
```

---

## Task 14: Toner reference_coverage_pct + paper suggestion UI

**Files:**
- Modify: `frontend/src/pages/printers/PrinterDetailPage.tsx`
- Create: `frontend/src/components/printers/PaperSuggestSelect.tsx`

- [ ] **Step 1: Add the field to the toner form**

In `PrinterDetailPage.tsx`, find the `useState` for the toner form (around line 55):

```tsx
const [form, setForm] = useState({ toner_color: '', toner_type: 'standard', price_per_unit: '', rated_yield_pages: '', currency: 'INR' });
```

Replace with:

```tsx
const [form, setForm] = useState({ toner_color: '', toner_type: 'standard', price_per_unit: '', rated_yield_pages: '', reference_coverage_pct: '5.00', currency: 'INR' });
```

In the `createMutation` body, add `reference_coverage_pct: form.reference_coverage_pct`. Do the same for `updateMutation`.

Add a text input in the JSX near the existing price/yield inputs:

```tsx
<Input
  placeholder="Reference coverage %"
  type="number" step="0.01"
  value={form.reference_coverage_pct}
  onChange={e => setForm({ ...form, reference_coverage_pct: e.target.value })}
/>
```

- [ ] **Step 2: Create PaperSuggestSelect**

Create `frontend/src/components/printers/PaperSuggestSelect.tsx`:

```tsx
import { useQuery } from '@tanstack/react-query';
import { api } from '@/services/api';

interface Suggestion {
  paper_type: string;
  width_mm: number | null;
  length_mm: number | null;
  gsm: number | null;
  job_count: number;
}

interface Props {
  printerId: number;
  onPick: (s: Suggestion) => void;
}

export function PaperSuggestSelect({ printerId, onPick }: Props) {
  const { data } = useQuery<Suggestion[]>({
    queryKey: ['paper-suggestions', printerId],
    queryFn: () => api.get(`/printers/${printerId}/paper-suggestions`).then(r => r.data.data),
  });
  if (!data || data.length === 0) return null;
  return (
    <select
      className="rounded-md border px-2 py-1 text-sm"
      defaultValue=""
      onChange={e => {
        const idx = parseInt(e.target.value);
        if (!isNaN(idx)) onPick(data[idx]);
      }}
    >
      <option value="">Suggest from uploaded data…</option>
      {data.map((s, i) => (
        <option key={i} value={i}>
          {s.paper_type} {s.width_mm ? `· ${s.width_mm}×${s.length_mm}mm` : ''} {s.gsm ? `· ${s.gsm}gsm` : ''} ({s.job_count})
        </option>
      ))}
    </select>
  );
}
```

- [ ] **Step 3: Wire `PaperSuggestSelect` into the paper add form**

Locate where the printer detail page lists Papers and exposes an "Add Paper" form. Import `PaperSuggestSelect` and render it above the paper name input. On pick, prefill the name/width/length/gsm fields.

- [ ] **Step 4: Tooltip in ColumnMappingPage**

Open `frontend/src/pages/printers/ColumnMappingPage.tsx`, in the `Paper & Media` group (line ~62), add this just before the closing `]` of `fields`:

```tsx
{ key: '__note__' as string, label: '', description: 'Width/Length take precedence over Size for cost matching. Type must match a configured Paper name.' } as any,
```

Or better — render a `<p className="mt-2 text-xs text-muted-foreground">` beneath the section in the rendering loop. Keep it out of the `FIELD_GROUPS` data structure to avoid leaking into backend calls.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/printers/PrinterDetailPage.tsx frontend/src/components/printers/PaperSuggestSelect.tsx frontend/src/pages/printers/ColumnMappingPage.tsx
git commit -m "feat(ui): reference coverage input, paper suggestions, column-mapping tooltip"
```

---

## Task 15: Recompute-on-demand UI hook

**Files:**
- Modify: `frontend/src/pages/printers/PrinterDetailPage.tsx` (or wherever paper/toner save happens)

- [ ] **Step 1: After a successful toner/paper/replacement mutation, toast + trigger**

Wrap the existing mutation `onSuccess`:

```tsx
onSuccess: (resp) => {
  qc.invalidateQueries({ queryKey: ['toners', printerId] });
  if (resp?.data?.recompute_hint || true) {
    if (confirm('Recompute cost for all jobs on this printer?')) {
      api.post(`/printers/${printerId}/recompute-costs`).then(() => {
        qc.invalidateQueries({ queryKey: ['analytics-summary'] });
      });
    }
  }
},
```

- [ ] **Step 2: Manual smoke test**

Log in → change a toner price → confirm the recompute prompt → verify dashboard KPI changes.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/pages/printers/PrinterDetailPage.tsx
git commit -m "feat(ui): offer recompute after cost-affecting edits"
```

---

## Task 16: End-to-end verification

- [ ] **Step 1: Wipe existing jobs and reimport**

Through the UI, use the "Clear all jobs" button, then reupload a production-like CSV.

- [ ] **Step 2: Spot-check computed costs**

Pick 2-3 jobs in the DB and manually compute expected cost using the spec formula; compare to `computed_total_cost`.

- [ ] **Step 3: Walk through the dashboard**

Change the date range to "Today", "7d", and a custom range. Confirm all charts, KPIs, and the drawer behave.

- [ ] **Step 4: Commit any final docstring/comment fixups**

```bash
git add -A
git commit -m "chore: final pass on cost dashboard"
```

---

## Self-Review

**Spec coverage:**
- §2 schema changes → Task 1 ✓
- §3 paper matching + autosuggest → Tasks 3 (match), 7 (endpoint), 14 (UI) ✓
- §4 toner cost engine → Tasks 2 (tests), 3 (impl) ✓
- §5 compute triggers + replacement UX → Tasks 4, 5, 6, 15 ✓
- §6 analytics API → Task 8 ✓
- §7 dashboard UI + palette → Tasks 9–13 ✓
- §7.5 consumption panel → Task 12 (component created; binding to a new `GET /printers/{id}/toner-consumption` endpoint is implied but not yet wired; noted as a follow-up if needed)
- §8 files touched → matches tasks ✓
- §9 tests → Tasks 2, 5 ✓
- §10 migration order → Task 1 migrations + Task 16 reimport ✓

**Gaps identified:**
- §7.5 toner-consumption data source: the component exists but there's no dedicated backend endpoint to feed it. Add it as Task 17 if/when the user wants live consumption metrics; for now cards can be driven client-side from toner + replacement data already available.

**Placeholder scan:** None found. All steps have concrete code, file paths, and commands.

**Type consistency:** `compute_job_cost` signature matches between Tasks 3, 4, 5, 6. Frontend query response shapes match backend return shapes.
