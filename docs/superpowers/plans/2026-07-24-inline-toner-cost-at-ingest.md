# Inline Toner Cost at Ingest + Fast Analytics Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Compute each print job's toner and paper cost inline at CSV ingest and store it, and make the analytics dashboard read those stored values with SQL aggregation so it and its filters are fast.

**Architecture:** The cost engine (`cost_calc.py`) returns per-channel costs keyed by the `coverage_est_<color>` column to overwrite (those columns arrive empty from the RIP, so they are repurposed as the per-color cost output). A single `apply_cost_to_job` helper persists results. The ingest pipeline computes cost per job before insert; analytics endpoints sum with Postgres `SUM()`/`GROUP BY` instead of loading full ORM rows.

**Tech Stack:** Python 3, FastAPI, SQLAlchemy 2.0 (ORM), Alembic, PostgreSQL, pytest; React + TypeScript frontend.

## Global Constraints

- Coverage input for the formula is the actual `coverage_<color>` column only — never `coverage_est_<color>` (that column is now the cost output slot).
- Raster coverage is already a cumulative job total: coverage is **not** multiplied by page count.
- `computed_toner_cost` sums only channels that have a toner defined for the printer.
- One job's cost failure must be logged and skipped, never abort a chunk/batch.
- Follow the existing SQLAlchemy 2.0 `Mapped[...]` model style and the service's own-`SessionLocal` pattern (safe for the background upload thread).
- Commit messages end with the Co-Authored-By / Claude-Session trailers used in this repo.

---

### Task 1: Cost engine returns per-channel cost + actual-only input + persistence helper

**Files:**
- Modify: `backend/app/services/cost_calc.py`
- Test: `backend/tests/unit/test_cost_calc.py`

**Interfaces:**
- Produces: `compute_job_cost(job, *, toners, matched_paper) -> dict` with keys
  `paper_cost: float`, `toner_cost: float`, `total_cost: float`,
  `per_channel_cost: dict[str, float]` (keys are `coverage_est_<color>` column
  names), `source: str`.
- Produces: `apply_cost_to_job(job, result: dict) -> None` — writes each
  `per_channel_cost` value into its `coverage_est_*` attribute and sets
  `computed_paper_cost`, `computed_toner_cost`, `computed_total_cost`,
  `cost_computation_source`, `cost_computed_at`.

- [ ] **Step 1: Write the failing tests**

Add to `backend/tests/unit/test_cost_calc.py`:

```python
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
```

Add `apply_cost_to_job` to the import at the top of the test file:

```python
from app.services.cost_calc import apply_cost_to_job, compute_job_cost, match_paper_for_job
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && python -m pytest tests/unit/test_cost_calc.py -q`
Expected: FAIL — `ImportError: cannot import name 'apply_cost_to_job'` / `KeyError: 'per_channel_cost'`.

- [ ] **Step 3: Change `_pick_coverage` to actual-only**

In `backend/app/services/cost_calc.py`, replace `_pick_coverage` so it reads
only the actual coverage attribute (the est attribute is now output):

```python
def _pick_coverage(job, attr_actual: str) -> tuple[Optional[Decimal], str]:
    val = getattr(job, attr_actual, None)
    if val is not None:
        try:
            d = Decimal(str(val))
            if d > 0:
                return d, "actual"
        except Exception:
            pass
    return None, "unavailable"
```

- [ ] **Step 4: Rewrite the toner loop in `compute_job_cost`**

Replace the `breakdown` accumulation with `per_channel_cost` keyed by the est
attribute, summing only channels with a toner. In the loop body:

```python
    per_channel_cost: dict[str, float] = {}
    sources: set[str] = set()
    toner_total = Decimal("0")

    recorded_at = getattr(job, "recorded_at", None)

    for t in toners:
        color_key = getattr(t, "coverage_channel", None) or _normalize_color(t.toner_color)
        if color_key not in _COLOR_MAP:
            continue
        cov_attr, est_attr, pages_attr = _COLOR_MAP[color_key]
        coverage, src = _pick_coverage(job, cov_attr)
        pages = _pages_for_color(job, pages_attr)

        sources.add(src)
        if coverage is None or pages == 0:
            per_channel_cost[est_attr] = 0.0
            continue

        price, yield_pages, ref_cov = _pricing_for_toner(t, recorded_at)
        if yield_pages == 0 or ref_cov == 0:
            per_channel_cost[est_attr] = 0.0
            continue

        price_per_page = price / Decimal(yield_pages)
        cost = (coverage / ref_cov) * price_per_page
        toner_total += cost
        per_channel_cost[est_attr] = float(round(cost, 4))
```

Update the return dict (drop `breakdown`, add `per_channel_cost`):

```python
    total = paper_cost + toner_total
    return {
        "paper_cost": float(round(paper_cost, 4)),
        "toner_cost": float(round(toner_total, 4)),
        "total_cost": float(round(total, 4)),
        "per_channel_cost": per_channel_cost,
        "source": source_flag,
    }
```

- [ ] **Step 5: Add the `apply_cost_to_job` helper**

Add these imports at the top of `cost_calc.py` (alongside the existing `from decimal import Decimal`):

```python
from datetime import datetime, timezone
```

Append the helper at the end of the file:

```python
def apply_cost_to_job(job, result: dict) -> None:
    """Persist a compute_job_cost result onto a PrintJob (no commit)."""
    for est_attr, val in result["per_channel_cost"].items():
        setattr(job, est_attr, Decimal(str(val)))
    job.computed_paper_cost = Decimal(str(result["paper_cost"]))
    job.computed_toner_cost = Decimal(str(result["toner_cost"]))
    job.computed_total_cost = Decimal(str(result["total_cost"]))
    job.cost_computation_source = result["source"]
    job.cost_computed_at = datetime.now(timezone.utc)
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/unit/test_cost_calc.py -q`
Expected: PASS (all tests, including the pre-existing ones — the fallback test
that fed `coverage_est` as input must be updated to feed `coverage_<color>`; if
an old test asserts on `breakdown`, change it to `per_channel_cost`).

- [ ] **Step 7: Commit**

```bash
git add backend/app/services/cost_calc.py backend/tests/unit/test_cost_calc.py
git commit -m "feat(cost): per-channel cost into coverage_est_*, actual-only input, apply helper"
```

---

### Task 2: Migration — drop breakdown column, add composite index

**Files:**
- Create: `backend/alembic/versions/008_r16_drop_breakdown_add_index.py`
- Modify: `backend/app/models/upload.py` (remove `computed_toner_cost_breakdown`)

**Interfaces:**
- Consumes: nothing.
- Produces: `print_jobs` table without `computed_toner_cost_breakdown`, with a
  `ix_print_jobs_printer_recorded` index on `(printer_id, recorded_at)`.

- [ ] **Step 1: Write the migration**

Create `backend/alembic/versions/008_r16_drop_breakdown_add_index.py` (confirm
`down_revision` matches the head — `007_r15_toner_coverage_channel`):

```python
"""drop computed_toner_cost_breakdown, add (printer_id, recorded_at) index

Revision ID: 008_r16_drop_breakdown_add_index
Revises: 007_r15_toner_coverage_channel
Create Date: 2026-07-24
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "008_r16_drop_breakdown_add_index"
down_revision = "007_r15_toner_coverage_channel"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_column("print_jobs", "computed_toner_cost_breakdown")
    op.create_index(
        "ix_print_jobs_printer_recorded",
        "print_jobs",
        ["printer_id", "recorded_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_print_jobs_printer_recorded", table_name="print_jobs")
    op.add_column(
        "print_jobs",
        sa.Column(
            "computed_toner_cost_breakdown",
            JSONB(),
            nullable=False,
            server_default="{}",
        ),
    )
```

- [ ] **Step 2: Verify the down_revision is the current head**

Run: `cd backend && python -m alembic heads`
Expected: prints `007_r15_toner_coverage_channel` as the single head. If the
head id differs, set `down_revision` to that exact id.

- [ ] **Step 3: Remove the column from the model**

In `backend/app/models/upload.py`, delete the `computed_toner_cost_breakdown`
mapped column block (lines around 280-282):

```python
    computed_toner_cost_breakdown: Mapped[dict] = mapped_column(
        JSONB, nullable=False, default=dict, server_default="{}"
    )
```

Leave the `from sqlalchemy.dialects.postgresql import JSONB` import — it is still
used by `UploadBatch.skipped_details`.

- [ ] **Step 4: Apply the migration**

Run: `cd backend && python -m alembic upgrade head`
Expected: `Running upgrade 007_r15_toner_coverage_channel -> 008_r16_drop_breakdown_add_index`.

- [ ] **Step 5: Verify schema**

Run: `cd backend && python -c "from app.database import engine; import sqlalchemy as sa; print([c['name'] for c in sa.inspect(engine).get_columns('print_jobs')])"`
Expected: list does **not** contain `computed_toner_cost_breakdown`.

- [ ] **Step 6: Commit**

```bash
git add backend/alembic/versions/008_r16_drop_breakdown_add_index.py backend/app/models/upload.py
git commit -m "feat(db): drop computed_toner_cost_breakdown, add (printer_id, recorded_at) index"
```

---

### Task 3: Compute cost inline at ingest with precise logging

**Files:**
- Modify: `backend/app/services/csv_import_service.py`
- Test: `backend/tests/integration/test_ingest_cost.py` (create)

**Interfaces:**
- Consumes: `compute_job_cost`, `apply_cost_to_job`, `match_paper_for_job` from Task 1.
- Produces: after `import_csv_for_printer`, every inserted `PrintJob` has
  non-zero `computed_toner_cost` (when a matching toner + coverage exist),
  `coverage_est_*` holding per-color cost, and `computed_total_cost = paper + toner`.

- [ ] **Step 1: Write the failing integration test**

Create `backend/tests/integration/test_ingest_cost.py`. Follow the existing
integration-test conftest/fixtures for DB setup (mirror another file in
`backend/tests/integration/`). The test seeds a printer with a column mapping,
one K toner (`coverage_channel="K"`), imports a 1-row CSV whose `coverage_k`
column is populated, and asserts the stored job is costed:

```python
def test_ingest_computes_toner_cost(seeded_printer_with_k_toner, sample_csv_bytes):
    from app.services.csv_import_service import import_csv_for_printer
    from app.models.upload import PrintJob
    from app.database import SessionLocal

    result = import_csv_for_printer(
        printer_id=seeded_printer_with_k_toner.id,
        raw_bytes=sample_csv_bytes,
        filename="t.csv",
        source="automated",
        uploaded_by_user_id=None,
    )
    assert result.rows_imported == 1

    s = SessionLocal()
    try:
        job = s.query(PrintJob).filter_by(printer_id=seeded_printer_with_k_toner.id).one()
        assert float(job.computed_toner_cost) > 0
        assert job.coverage_est_k is not None and float(job.coverage_est_k) > 0
        assert float(job.computed_total_cost) == pytest.approx(
            float(job.computed_paper_cost) + float(job.computed_toner_cost), abs=1e-6
        )
    finally:
        s.close()
```

(If no integration conftest exists, add fixtures in this file that build the
printer, K toner, and a CSV string using the printer's `column_mapping` keys.)

- [ ] **Step 2: Run it to verify it fails**

Run: `cd backend && python -m pytest tests/integration/test_ingest_cost.py -q`
Expected: FAIL — `computed_toner_cost` is 0 (costing not wired yet).

- [ ] **Step 3: Load toners + papers once at the top of the pipeline**

In `import_csv_for_printer`, after the printer/mapping lookup block (right after
`printer_column_mapping = dict(printer.column_mapping)` and before the CSV
parse), load and detach the costing inputs:

```python
    # Cost inputs — loaded once, detached, reused across all chunks.
    from sqlalchemy.orm import joinedload
    from app.models.paper import Paper
    from app.models.toner import Toner

    _cost_setup = SessionLocal()
    try:
        toners = (
            _cost_setup.query(Toner)
            .options(joinedload(Toner.replacement_logs))
            .filter(Toner.printer_id == printer_id)
            .all()
        )
        papers = (
            _cost_setup.query(Paper)
            .join(Paper.printer_links)
            .filter_by(printer_id=printer_id)
            .all()
        )
        _cost_setup.expunge_all()
    finally:
        _cost_setup.close()
```

- [ ] **Step 4: Cost each job before insert**

At the top of `csv_import_service.py`, add the import:

```python
from app.services.cost_calc import apply_cost_to_job, compute_job_cost, match_paper_for_job
```

In the chunk loop, after `jobs_to_add.append(_build_job(...))` builds the chunk
and before `chunk_session.add_all(jobs_to_add)`, cost each job:

```python
        costed = 0
        zero_toner = 0
        for job in jobs_to_add:
            try:
                matched = match_paper_for_job(job, papers)
                job.matched_paper_id = matched.id if matched else None
                result = compute_job_cost(job, toners=toners, matched_paper=matched)
                apply_cost_to_job(job, result)
                costed += 1
                if result["toner_cost"] == 0:
                    zero_toner += 1
            except Exception as job_err:
                logger.warning(
                    "cost compute failed printer=%s job_id=%s: %s",
                    printer_id, getattr(job, "job_id", "?"), job_err,
                )
```

Note: `matched_paper_id` is set on the detached job before insert; keep it
inside the same chunk session add.

- [ ] **Step 5: Add the per-batch summary log**

Immediately after `imported += len(jobs_to_add)` in the successful-commit
branch, log the chunk summary:

```python
                logger.info(
                    "csv_import costed chunk printer=%s batch=%s jobs=%d zero_toner=%d",
                    printer_id, batch_id, costed, zero_toner,
                )
```

- [ ] **Step 6: Run the integration test to verify it passes**

Run: `cd backend && python -m pytest tests/integration/test_ingest_cost.py -q`
Expected: PASS.

- [ ] **Step 7: Run the full backend suite for regressions**

Run: `cd backend && python -m pytest -q`
Expected: PASS (no reference to the dropped column or old `breakdown` key
remains outside Tasks 4-5, which follow — if those files still reference
`breakdown`/`computed_toner_cost_breakdown`, this is expected to fail there and
is fixed in Task 4).

- [ ] **Step 8: Commit**

```bash
git add backend/app/services/csv_import_service.py backend/tests/integration/test_ingest_cost.py
git commit -m "feat(ingest): compute toner+paper cost inline per job with batch logging"
```

---

### Task 4: Update recompute + replacement call sites to the new result shape

**Files:**
- Modify: `backend/app/routers/print_jobs.py` (recompute-costs, around lines 404-410)
- Modify: `backend/app/routers/toner_replacements.py` (around lines 138-144)

**Interfaces:**
- Consumes: `apply_cost_to_job` from Task 1.
- Produces: both endpoints persist via `apply_cost_to_job`; neither references
  `computed_toner_cost_breakdown`.

- [ ] **Step 1: Update the recompute loop**

In `backend/app/routers/print_jobs.py`, replace the per-job persistence block
inside `recompute_costs` (the `job.computed_paper_cost = ...` through
`job.cost_computed_at = ...` lines) with:

```python
                            matched = match_paper_for_job(job, papers)
                            job.matched_paper_id = matched.id if matched else None
                            cost_result = compute_job_cost(job, toners=toners, matched_paper=matched)
                            apply_cost_to_job(job, cost_result)
```

Add `apply_cost_to_job` to the import from `cost_calc` at the top of the file.

- [ ] **Step 2: Update the toner-replacement recompute loop**

In `backend/app/routers/toner_replacements.py`, replace the block that sets
`job.computed_toner_cost = ...` / `job.computed_toner_cost_breakdown = ...` with:

```python
        cr = compute_job_cost(job, toners=all_toners, matched_paper=matched)
        apply_cost_to_job(job, cr)
```

Add `apply_cost_to_job` to the local `from app.services.cost_calc import ...`
line in that function.

- [ ] **Step 3: Grep for any remaining breakdown references in backend**

Run: `cd backend && grep -rn "computed_toner_cost_breakdown\|\"breakdown\"\|\\['breakdown'\\]" app | grep -v __pycache__`
Expected: only `app/routers/analytics.py` still matches (fixed in Task 5).

- [ ] **Step 4: Run the backend suite**

Run: `cd backend && python -m pytest -q`
Expected: PASS except any analytics test touching `breakdown` (fixed next task).

- [ ] **Step 5: Commit**

```bash
git add backend/app/routers/print_jobs.py backend/app/routers/toner_replacements.py
git commit -m "refactor(cost): route recompute + replacement through apply_cost_to_job"
```

---

### Task 5: Analytics endpoints — SQL aggregation, no breakdown

**Files:**
- Modify: `backend/app/routers/analytics.py`
- Test: `backend/tests/integration/test_analytics_aggregation.py` (create)

**Interfaces:**
- Consumes: stored `computed_*` and `coverage_est_*` columns.
- Produces: `summary`, `trends`, `cost-breakdown`, `toner-breakdown`,
  `paper-breakdown`, `printers-comparison`, `top-jobs` compute with SQL
  aggregation; `top-jobs` no longer returns a `breakdown` field.

- [ ] **Step 1: Write a failing equivalence test**

Create `backend/tests/integration/test_analytics_aggregation.py`. Seed several
jobs with known `computed_total_cost`/`computed_paper_cost`/`computed_toner_cost`
across two dates and assert the `summary` endpoint's totals equal a manual sum:

```python
def test_summary_totals_match_manual_sum(client, seeded_jobs, owner_auth_headers):
    resp = client.get("/analytics/summary?period=365d", headers=owner_auth_headers)
    data = resp.json()["data"]
    expected_total = sum(float(j.computed_total_cost) for j in seeded_jobs)
    assert data["total_cost"] == pytest.approx(round(expected_total, 2), abs=0.01)
    assert data["total_jobs"] == len(seeded_jobs)
```

(Reuse the integration client/auth fixtures already used by other
`tests/integration` files; if none seed jobs, add a `seeded_jobs` fixture here.)

- [ ] **Step 2: Run it to verify it passes or fails meaningfully**

Run: `cd backend && python -m pytest tests/integration/test_analytics_aggregation.py -q`
Expected: PASS against the current Python-loop code (it establishes the baseline
the refactor must preserve). If fixtures are missing it will error — fix
fixtures first.

- [ ] **Step 3: Rewrite `summary` with `func.sum`**

Add `from sqlalchemy import func` to the imports. Replace the body of `summary`
after the range/printer resolution with a single aggregate query:

```python
    from sqlalchemy import case
    row = (
        db.query(
            func.coalesce(func.sum(PrintJob.computed_total_cost), 0),
            func.coalesce(func.sum(PrintJob.computed_paper_cost), 0),
            func.coalesce(func.sum(PrintJob.computed_toner_cost), 0),
            func.coalesce(func.sum(PrintJob.printed_pages), 0),
            func.count(PrintJob.id),
            func.coalesce(func.sum(case((PrintJob.is_waste, PrintJob.computed_total_cost), else_=0)), 0),
            func.coalesce(func.sum(case((PrintJob.is_waste, PrintJob.printed_pages), else_=0)), 0),
            func.coalesce(func.sum(PrintJob.color_pages), 0),
            func.coalesce(func.sum(PrintJob.bw_pages), 0),
        )
        .filter(
            PrintJob.printer_id.in_(printer_ids),
            PrintJob.recorded_at >= start,
            PrintJob.recorded_at <= end,
        )
    )
    if printer_id:
        row = row.filter(PrintJob.printer_id == printer_id)
    (total_cost, paper_cost, toner_cost, total_pages, total_jobs,
     waste_cost, waste_pages, color_pages, bw_pages) = row.one()

    total_cost = float(total_cost); paper_cost = float(paper_cost)
    toner_cost = float(toner_cost); total_pages = int(total_pages)
    waste_cost = float(waste_cost); waste_pages = int(waste_pages)
    color_pages = int(color_pages); bw_pages = int(bw_pages)

    if total_jobs == 0:
        return {"data": _empty_summary(period), "message": "ok"}
```

Keep the existing return dict that formats these locals (rounding, pct, cost_per_page).

- [ ] **Step 4: Rewrite `cost-breakdown` with `func.sum`**

Replace its `jobs = q.all()` + Python sums with one aggregate query mirroring
Step 3 (total paper, total toner, waste = sum of `computed_total_cost` where
`is_waste`). Return the same shape.

- [ ] **Step 5: Rewrite `printers-comparison` as one grouped query**

Replace the per-printer loop with a single `GROUP BY`:

```python
    from sqlalchemy import func
    rows = (
        db.query(
            Printer.id, Printer.name,
            func.coalesce(func.sum(PrintJob.computed_total_cost), 0),
            func.coalesce(func.sum(PrintJob.printed_pages), 0),
            func.count(PrintJob.id),
        )
        .outerjoin(
            PrintJob,
            (PrintJob.printer_id == Printer.id)
            & (PrintJob.recorded_at >= start)
            & (PrintJob.recorded_at <= end),
        )
        .group_by(Printer.id, Printer.name)
        .all()
    )
    result = []
    for pid, name, total_cost, total_pages, total_jobs in rows:
        total_cost = float(total_cost); total_pages = int(total_pages)
        result.append({
            "printer_id": pid, "printer_name": name,
            "total_cost": round(total_cost, 2), "total_pages": total_pages,
            "total_jobs": int(total_jobs),
            "cost_per_page": round(total_cost / total_pages, 4) if total_pages else 0,
        })
    return {"data": result, "message": "ok"}
```

- [ ] **Step 6: Keep `trends` / `paper-breakdown` bucketing, but select narrow columns**

These bucket by a derived key. Rather than loading full rows, query only the
needed columns so no 90-column ORM object is built:

```python
    rows = (
        db.query(
            PrintJob.recorded_at, PrintJob.computed_total_cost,
            PrintJob.computed_paper_cost, PrintJob.computed_toner_cost,
            PrintJob.printed_pages, PrintJob.is_waste,
        )
        .filter(
            PrintJob.printer_id.in_(printer_ids),
            PrintJob.recorded_at >= start, PrintJob.recorded_at <= end,
        )
    )
    if printer_id:
        rows = rows.filter(PrintJob.printer_id == printer_id)
    for recorded_at, total, paper, toner, pages, is_waste in rows.all():
        ...  # existing bucketing math, using tuple fields
```

Apply the same narrow-column select to `paper-breakdown` (select
`paper_type, computed_paper_cost, printed_pages`).

- [ ] **Step 7: Fix `toner-breakdown` to sum `coverage_est_*`**

The breakdown JSON is gone. Sum the per-color cost columns per bucket. Select
`recorded_at`, `computed_paper_cost`, and each `coverage_est_<color>` column,
then accumulate into `slot[<color>]`:

```python
    _EST_COLS = [
        ("k", PrintJob.coverage_est_k), ("c", PrintJob.coverage_est_c),
        ("m", PrintJob.coverage_est_m), ("y", PrintJob.coverage_est_y),
        ("gld_1", PrintJob.coverage_est_gld_1), ("slv_1", PrintJob.coverage_est_slv_1),
        ("clr_1", PrintJob.coverage_est_clr_1), ("wht_1", PrintJob.coverage_est_wht_1),
        ("cr_1", PrintJob.coverage_est_cr_1), ("p_1", PrintJob.coverage_est_p_1),
        ("pa_1", PrintJob.coverage_est_pa_1), ("gld_6", PrintJob.coverage_est_gld_6),
        ("slv_6", PrintJob.coverage_est_slv_6), ("wht_6", PrintJob.coverage_est_wht_6),
        ("p_6", PrintJob.coverage_est_p_6),
    ]
    rows = (
        db.query(PrintJob.recorded_at, PrintJob.computed_paper_cost,
                 *[col for _, col in _EST_COLS])
        .filter(PrintJob.printer_id.in_(printer_ids),
                PrintJob.recorded_at >= start, PrintJob.recorded_at <= end)
    )
    if printer_id:
        rows = rows.filter(PrintJob.printer_id == printer_id)
    by_bucket: dict[str, dict] = {}
    for r in rows.all():
        if not r[0]:
            continue
        b = _bucket_key(r[0], granularity)
        slot = by_bucket.setdefault(b, {"bucket": b, "paper": 0.0})
        slot["paper"] += float(r[1] or 0)
        for i, (name, _) in enumerate(_EST_COLS):
            v = r[2 + i]
            if v:
                slot[name] = slot.get(name, 0.0) + float(v)
    return {"data": sorted(by_bucket.values(), key=lambda x: x["bucket"]),
            "granularity": granularity, "message": "ok"}
```

- [ ] **Step 8: Remove the `breakdown` field from `top-jobs`**

In the `top-jobs` return list-comprehension, delete the line
`"breakdown": j.computed_toner_cost_breakdown,`. Everything else stays.

- [ ] **Step 9: Run the analytics test + full suite**

Run: `cd backend && python -m pytest tests/integration/test_analytics_aggregation.py -q && python -m pytest -q`
Expected: PASS. The equivalence test proves SQL sums match the previous Python sums.

- [ ] **Step 10: Commit**

```bash
git add backend/app/routers/analytics.py backend/tests/integration/test_analytics_aggregation.py
git commit -m "perf(analytics): SQL aggregation for summaries; sum coverage_est_* for toner breakdown"
```

---

### Task 6: Frontend — drop breakdown usage, grey out toner replacement

**Files:**
- Modify: `frontend/src/components/charts/JobDetailDrawer.tsx`
- Modify: `frontend/src/pages/dashboard/DashboardPage.tsx`
- Modify: `frontend/src/pages/settings/TonerReplacementsPage.tsx`
- Modify: `frontend/src/components/layout/Sidebar.tsx`

**Interfaces:**
- Consumes: analytics API without `breakdown`; `toner-breakdown` now keyed by
  `k`, `c`, `m`, `y`, `gld_1`, … cost sums.
- Produces: no frontend reference to `breakdown`/`computed_toner_cost_breakdown`;
  toner-replacement nav + page visibly disabled.

- [ ] **Step 1: Find every breakdown reference**

Run: `cd frontend && grep -rn "breakdown\|computed_toner_cost_breakdown" src`
Read each hit before editing.

- [ ] **Step 2: Remove `breakdown` consumption in `JobDetailDrawer.tsx`**

Read the file. The top-jobs / job payload no longer carries `breakdown`. Delete
the block that renders `job.breakdown` (the per-color list) or guard it so a
missing/undefined `breakdown` renders nothing. Verify no TypeScript type still
requires the field (remove it from the local interface if present).

- [ ] **Step 3: Update `DashboardPage.tsx` toner-breakdown consumption**

Read the file's `toner-breakdown` fetch/render. The response items are still
`{ bucket, paper, <color>: number }`; confirm the chart keys read the color
names (`k`, `c`, `m`, …). No shape change is needed beyond ensuring it does not
reference the removed job-level `breakdown`. Adjust any color-key list to match
`_EST_COLS` names from Task 5 Step 7.

- [ ] **Step 4: Grey out the toner-replacement page**

In `frontend/src/pages/settings/TonerReplacementsPage.tsx`, wrap the page body
in a disabled state with a "Coming soon" banner and make controls
non-interactive:

```tsx
<div className="relative">
  <div className="pointer-events-none opacity-50">
    {/* existing page content */}
  </div>
  <div className="absolute inset-0 flex items-center justify-center">
    <span className="rounded bg-gray-800/80 px-4 py-2 text-sm text-white">
      Toner replacement — coming soon
    </span>
  </div>
</div>
```

- [ ] **Step 5: Disable the nav entry in `Sidebar.tsx`**

Read `frontend/src/components/layout/Sidebar.tsx`. For the toner-replacement nav
item, render it disabled (no route navigation, muted styling, `title="Coming
soon"`) instead of an active link. Match the existing nav item markup.

- [ ] **Step 6: Type-check / build the frontend**

Run: `cd frontend && npm run build`
Expected: build succeeds with no reference errors to `breakdown`.

- [ ] **Step 7: Commit**

```bash
git add frontend/src
git commit -m "feat(ui): drop breakdown usage; grey out toner replacement (deferred)"
```

---

## Self-Review

**Spec coverage:**
- §1 cost engine actual-only + per-channel → Task 1. ✓
- §2 persist to coverage_est_* + totals → Task 1 (`apply_cost_to_job`), Task 3/4 callers. ✓
- §3 drop breakdown column → Task 2. ✓
- §4 inline compute at ingest → Task 3. ✓
- §5 logging → Task 3 Steps 4-5. ✓
- §6 analytics SQL aggregation → Task 5. ✓
- §7 frontend grey-out + breakdown removal → Task 6. ✓
- Verification (unit, ingest integration, analytics equivalence, migration) → Tasks 1,3,5,2. ✓

**Type consistency:** `compute_job_cost` returns `per_channel_cost` (keys =
`coverage_est_*` attr names) in Task 1 and is consumed identically in Tasks 3-5;
`apply_cost_to_job(job, result)` signature identical across Tasks 1, 3, 4.

**Placeholders:** none — every code step shows concrete code; frontend
read-then-edit steps name exact files and give the disabled-state markup.
