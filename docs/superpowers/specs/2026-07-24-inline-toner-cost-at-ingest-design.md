# Inline Toner Cost at Ingest + Fast Analytics

**Date:** 2026-07-24
**Status:** Approved (design)

## Problem

Two things make the dashboard slow and empty:

1. **Costs are never computed at ingest.** `import_csv_for_printer`
   (`backend/app/services/csv_import_service.py`) inserts every `PrintJob` with
   `computed_toner_cost = 0`, `computed_total_cost = 0`. The headless n8n
   `/import` endpoint returns without triggering any cost pass. Costs only
   become non-zero when a user manually runs the SSE `/recompute-costs`
   endpoint. So after a Drive file is ingested, the dashboard shows zero.

2. **Analytics sums in Python.** Every analytics endpoint
   (`backend/app/routers/analytics.py`) does `q.all()` — pulling full ~90-column
   `PrintJob` ORM rows into memory — then loops in Python to sum
   `computed_total_cost`, `computed_paper_cost`, etc. This is slow and gets
   slower as jobs accumulate.

The cost formula itself is correct. The defect is *when* and *how* costs are
computed and read.

## Goal

When a CSV lands (n8n `/import` **or** manual upload), compute each job's cost
**inline as the row is inserted** — no zeros left behind, no second pass. Store
the results in columns. Make the dashboard read those columns with SQL
aggregation so it and its filters are fast. Focus on **toner cost** (and paper
cost, which falls out of the same pass); defer toner replacement.

## Key data fact

The `coverage_est_<color>` columns arrive **empty** from the sheet — the RIP
does not populate them. The real coverage input is the actual
`coverage_<color>` column. Therefore the `coverage_est_<color>` columns can be
**repurposed as the per-color cost output** without destroying any input, and
in-place recompute (which reads `coverage_<color>`) still works.

## Design

### 1. Cost engine (`backend/app/services/cost_calc.py`)

**Coverage input becomes actual-only.** `_pick_coverage` currently prefers
`coverage_<color>` then falls back to `coverage_est_<color>`. Remove the
fallback — read `coverage_<color>` only. The est column is now an output slot,
so falling back to it would read a cost as if it were coverage.

**Per-color cost**, unchanged formula, for each toner resolved by
`coverage_channel`:

```
coverage       = coverage_<color>                       # actual %, already a job total
price_per_page = price_per_unit / rated_yield_pages
cost_<color>   = (coverage / reference_coverage_pct) × price_per_page
```

Guards (any → `cost_<color> = 0`): the color has 0 relevant pages,
`coverage_<color>` empty/0, or `rated_yield_pages` / `reference_coverage_pct`
is 0. Coverage is **not** multiplied by page count — the raster value is already
the cumulative job total. K's page-guard is `color_pages + bw_pages`; C/M/Y use
`color_pages`; specialty channels use their own page columns (unchanged
`_COLOR_MAP`).

`compute_job_cost` returns, instead of a `breakdown` dict, a
`per_channel_cost: dict[coverage_est_attr -> float]` keyed by the
`coverage_est_<color>` column name to write, plus `toner_cost`, `paper_cost`,
`total_cost`, and `source`. `toner_cost` is the sum over **only the channels
that have a toner** (a color with coverage but no toner contributes nothing —
never sum leftover raw percentages).

**Paper cost**, unchanged:
```
computed_paper_cost = printed_sheets × matched_paper.price_per_sheet × counter_multiplier
```
`0` when no paper matches. Paper is matched via `match_paper_for_job` against
the printer's papers (`printer_papers` → `papers`). `counter_multiplier` is kept
(defaults to 1).

### 2. Persisting results on the job

Per job, after computing:

- Write each `cost_<color>` into its `coverage_est_<color>` column.
- `computed_toner_cost` = Σ of those per-channel costs.
- `computed_paper_cost` = paper formula above.
- `computed_total_cost` = `computed_paper_cost + computed_toner_cost`.
- `cost_computation_source` = existing source flag.
- `cost_computed_at` = now.

### 3. Drop `computed_toner_cost_breakdown`

New Alembic migration (next after `007_r15_toner_coverage_channel.py`):

- Drop the `computed_toner_cost_breakdown` JSONB column from `print_jobs`.
- Downgrade re-adds it (`JSONB NOT NULL DEFAULT '{}'`).

Remove the column from `PrintJob` (`backend/app/models/upload.py`) and every
reader. The per-color detail now lives in the `coverage_est_*` columns.

### 4. Inline computation at ingest (`csv_import_service.py`)

`_build_job` already parses `coverage_<color>` and the toner-relevant page
columns. Extend the import pipeline so that, per chunk, after building the
`PrintJob` objects and **before** `add_all`:

1. Load the printer's toners (with `replacement_logs`) and papers **once** at
   the start of `import_csv_for_printer`, detached, reused for all chunks.
2. For each job, run `match_paper_for_job` + `compute_job_cost`, then set
   `matched_paper_id`, the `coverage_est_*` costs, and the three `computed_*`
   columns.
3. Insert as today.

This runs inside the existing background thread for manual upload and inside the
`/import` request for n8n — both already call `import_csv_for_printer`, so both
get costs for free. No separate recompute step.

### 5. Logging

At the ingest cost step, emit:

- One INFO summary per batch: printer id, batch id, rows imported, jobs costed,
  jobs with zero toner cost, elapsed ms.
- One WARNING per job whose cost computation raised, with `job_id`, the channel
  being processed, and the offending value. A single job's failure must not
  abort the chunk — it is logged, its cost stays 0, and the import continues.

Use the module logger already present in the service.

### 6. Analytics performance (`analytics.py`)

Replace `q.all()` + Python summation with Postgres aggregation in every
endpoint:

- `summary`, `cost-breakdown`: `func.sum(...)` over the filtered query in one
  round trip (total, paper, toner, waste, pages, color/bw pages).
- `trends`, `toner-breakdown`, `paper-breakdown`: `GROUP BY` the bucket /
  paper_type expression in SQL rather than bucketing in Python.
- `printers-comparison`: single grouped query by `printer_id` instead of a
  per-printer loop of `.all()`.
- `top-jobs`: already SQL-ordered + limited; drop the removed `breakdown` field.

`toner-breakdown` sums the `coverage_est_*` columns per bucket (they now hold
per-color cost) instead of unpacking the dropped JSON.

The existing `(printer_id)` and `(recorded_at)` indexes back these filters. Add
a composite `(printer_id, recorded_at)` index on `print_jobs` in the same
migration if not already present, since every analytics filter uses both.

### 7. Frontend

- Grey out / disable the **toner replacement** UI (deferred). Mark it "coming
  soon"; keep it non-interactive.
- Remove any dashboard reference to the dropped `breakdown` field; the per-color
  toner chart consumes the `toner-breakdown` endpoint's `coverage_est_*` sums.
- Cost **recompute** stays functional (inputs preserved), so its button remains.

## Verification

- `backend/tests/unit/test_cost_calc.py`:
  - a toner with `coverage_channel="K"`, `coverage_k` set, `coverage_est_k`
    empty → `per_channel_cost["coverage_est_k"]` is non-zero and equals the
    formula; `toner_cost` equals the sum over channels with toners.
  - a color with coverage but no toner contributes 0 to `toner_cost`.
  - `coverage_<color>` empty/0 → that color's cost is 0 (guard).
- Ingest integration: import a sample CSV via `import_csv_for_printer`; assert
  the inserted jobs have non-zero `computed_toner_cost`, `coverage_est_*`
  holding costs, and `computed_total_cost = paper + toner`.
- Analytics: `summary` over a seeded set returns the same totals as a manual
  Python sum, proving the SQL aggregation is equivalent, and issues a bounded
  number of queries (no per-row load).
- Migration: upgrade drops `computed_toner_cost_breakdown`; downgrade re-adds
  it. `(printer_id, recorded_at)` index present after upgrade.
- Manual: drop a CSV through the n8n `/import` path, then open the dashboard —
  toner and paper cost are non-zero without any manual recompute.

## Out of scope

- No change to the raster-coverage formula or the `coverage_channel` mapping.
- No toner-replacement work (UI greyed out).
- No CSV column-mapping changes.
- No new caching layer — SQL aggregation on indexed columns is the performance
  fix for this version.
