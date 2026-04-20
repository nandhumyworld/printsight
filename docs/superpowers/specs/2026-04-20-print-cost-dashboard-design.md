# Print Cost Calculation & Dashboard — Design

**Date:** 2026-04-20
**Status:** Draft — pending user review
**Scope:** End-to-end cost attribution for each print job (paper + toner based on raster coverage), historical toner pricing via replacement logs, paper matching (width × length × gsm + type), and a colorful dashboard with flexible date range.

---

## 1. Goals

For every print job loaded from a printer CSV, produce:

1. **Paper cost** — derived from the matched `Paper` row (width, length, gsm tolerance + type match).
2. **Toner cost per color** — derived from raster coverage % vs the cartridge's reference coverage rating, priced using the cartridge that was installed at the time the job was printed (`toner_replacement_logs`).
3. **Total cost** — paper + sum of toner colors.
4. **Dashboard / analytics** — show cost per job, per day, per week, per month, across a user-selected custom date range, broken down by paper vs each toner color, with colorful visuals.

Out of scope for this iteration: electricity / maintenance / labour cost, multi-currency conversion, paper-stock inventory tracking.

---

## 2. Data Model Changes

### 2.1 `toners` — add reference coverage %

```sql
ALTER TABLE toners
  ADD COLUMN reference_coverage_pct NUMERIC(5,2) NOT NULL DEFAULT 5.00;
```

- Backfill existing rows to `5.00` (industry standard CMYK). Specialty toners (white, clear, gold, silver, etc.) are editable per toner; common values are 10–20%.
- UI: expose on the toner edit form with a tooltip: *"Assumed coverage % the cartridge is rated at. 5% for CMYK is standard; adjust for specialty toners per manufacturer datasheet."*

### 2.2 `toner_replacement_logs` — freeze reference coverage at replacement

```sql
ALTER TABLE toner_replacement_logs
  ADD COLUMN cartridge_reference_coverage_pct NUMERIC(5,2) NOT NULL DEFAULT 5.00;
```

- At replacement time, copy the current `toners.reference_coverage_pct` into this column so that rerating the toner later doesn't retroactively change historical costs.

### 2.3 `print_jobs` — cost metadata

```sql
ALTER TABLE print_jobs
  ADD COLUMN computed_toner_cost_breakdown JSONB NOT NULL DEFAULT '{}',
  ADD COLUMN cost_computed_at TIMESTAMPTZ NULL,
  ADD COLUMN cost_computation_source VARCHAR(20) NULL;
```

- `computed_toner_cost_breakdown` example: `{"k": 0.1203, "c": 0.0812, "m": 0.0730, "y": 0.0650, "gld_1": 0.0000}`. Keys mirror the coverage-column suffixes.
- `cost_computation_source` ∈ `{"actual", "estimation", "mixed", "unavailable"}` — whether the calc used `coverage_*` (actual), `coverage_est_*` (estimation), a mix, or had no coverage data.
- `cost_computed_at` is stamped on each compute; used by the recompute endpoint to find stale jobs.

### 2.4 No `papers` schema change

The perceived "duplication" on the paper column-mapping page (`paper_type` / `media_name` / `paper_size` / `paper_width_mm` / `paper_length_mm`) is by design: each is a different representation from the CSV source. Resolution is UX-only — see §5.

---

## 3. Paper Matching & Cost

### 3.1 Matching rule

When a print job is imported, attempt to set `print_jobs.matched_paper_id` by matching, in priority order:

1. **Exact name match** — `job.paper_type` equals `paper.name` (case-insensitive) AND `job.paper_gsm` falls within `[paper.gsm_min, paper.gsm_max]` AND width & length within tolerance.
2. **Dimensional match** — `job.paper_width_mm` within `paper.width_mm ± paper.width_tolerance_mm`, `job.paper_length_mm` within `paper.length_mm ± paper.length_tolerance_mm`, and gsm within range. Type can be blank/any.
3. **Name-only fallback** — paper type name matches but dimensions are missing from the CSV.

If multiple papers match, pick the one with the tightest combined dimensional delta. If none match, `matched_paper_id = NULL` and `computed_paper_cost = 0` with source `"unmatched"`.

### 3.2 Paper cost formula

```
paper_cost = matched_paper.price_per_sheet
           × printed_sheets
           × matched_paper.counter_multiplier
```

`printed_sheets` already accounts for duplex (one sheet = two pages). `counter_multiplier` handles stocks that count as >1 click (e.g. heavy stock = 1.5×).

### 3.3 Paper autosuggest UI

On the **Papers → Add/Edit** form, mimic the toner-color flow:

- A **"Suggest from CSV data"** dropdown populated from a new endpoint `GET /printers/{id}/paper-suggestions`. Backend query:

  ```sql
  SELECT paper_type,
         paper_width_mm, paper_length_mm,
         paper_gsm,          -- nullable until we capture it (see §3.4)
         COUNT(*) as job_count
    FROM print_jobs
   WHERE printer_id = :pid
     AND paper_type IS NOT NULL
  GROUP BY paper_type, paper_width_mm, paper_length_mm, paper_gsm
  ORDER BY job_count DESC
  ```

- Selecting a suggestion fills in `name`, `width_mm`, `length_mm`, and `gsm_min`/`gsm_max` (= gsm ±5). User edits tolerances and price before saving.

### 3.4 Paper GSM capture

Column mapping already has `paper_gsm` as a target field (present in the model). Audit the Fuji mapping JSON — if the source CSV exposes GSM as a column, add it to `resourses/column_mapping_ed_printer.json`. If not, GSM stays nullable; matching rule 2 relaxes the gsm check when nullable on either side.

---

## 4. Toner Cost Engine

### 4.1 Mapping pages → toner colors

Each CSV row gives pages printed with each toner. We account for colors independently:

| Toner color | Pages source column         |
| ----------- | --------------------------- |
| K           | `color_pages + bw_pages`    |
| C           | `color_pages`               |
| M           | `color_pages`               |
| Y           | `color_pages`               |
| GLD #1      | `gold_pages`                |
| SLV #1      | `silver_pages`              |
| CLR #1      | `clear_pages`               |
| WHT #1      | `white_pages`               |
| CR #1       | `texture_pages`             |
| P #1        | `pink_pages`                |
| PA #1       | `pa_pages`                  |
| GLD #6      | `gold_6_pages`              |
| SLV #6      | `silver_6_pages`            |
| WHT #6      | `white_6_pages`             |
| P #6        | `pink_6_pages`              |

For each color present on `printer.toners`, look up the corresponding coverage:

- Prefer `coverage_<suffix>` (actual raster coverage)
- Fall back to `coverage_est_<suffix>` (estimation) when actual is null/zero
- If neither exists → that color contributes 0 and `cost_computation_source` includes `"estimation"` or `"unavailable"` as appropriate.

### 4.2 Pricing window — which cartridge was installed

Given `job.recorded_at`, for each toner color on the printer:

```
log = latest TonerReplacementLog where
        toner.printer_id = printer_id
    AND toner.toner_color = color
    AND replaced_at <= job.recorded_at

if log exists:
    price       = log.cartridge_price_per_unit
    rated_yield = log.cartridge_rated_yield_pages
    ref_cov_pct = log.cartridge_reference_coverage_pct
else:
    # no log yet — use the current toner defaults
    price       = toner.price_per_unit
    rated_yield = toner.rated_yield_pages
    ref_cov_pct = toner.reference_coverage_pct
```

### 4.3 Cost formula (per color, per job)

```
price_per_page_at_ref = price / rated_yield          # cost assuming ref_cov_pct coverage
coverage              = coverage_actual ?? coverage_est   # in percent (0-100)
pages                 = mapping from §4.1
color_cost            = (coverage / ref_cov_pct) × price_per_page_at_ref × pages
```

Sum across all active toner colors → `computed_toner_cost`. Persist per-color breakdown to `computed_toner_cost_breakdown`.

### 4.4 Totals

```
computed_total_cost = computed_paper_cost + computed_toner_cost
```

---

## 5. Compute Triggers & Recompute Flow

### 5.1 On CSV upload

Extend `print_jobs.upload_csv` — after the row is flushed, call `compute_job_cost(job)` and update the computed columns before the batch commit. Paper matching also runs inside this step (currently skipped — jobs get `matched_paper_id = NULL`).

### 5.2 Recompute endpoint

```
POST /printers/{id}/recompute-costs
Body: { "from_date": "2026-04-01T00:00:00Z"?, "to_date": "..."?, "batch_id": int? }
```

Recomputes cost for all matching jobs. Returns `{rows_updated, elapsed_ms}`. Used by:

- Toner price or reference-coverage edit → recompute all jobs for that printer from the cartridge's first replacement onward.
- New toner replacement log → recompute jobs in that cartridge's window.
- Paper price or dimensional edit → recompute jobs where `matched_paper_id = that_paper`.

UI triggers this with a toast: *"Recompute N affected jobs?"* after any cost-affecting edit is saved.

### 5.3 Toner replacement UX

Confirm the existing replacement form uses a **datetime-local input** (not just today). The log must capture the exact `replaced_at` so cost attribution windows are correct. If the form is date-only, upgrade it.

---

## 6. Analytics API

All existing routes (`/analytics/summary`, `/analytics/trends`, `/analytics/cost-breakdown`, `/analytics/printers-comparison`) gain:

- `start_date`, `end_date` (ISO datetime, optional — take precedence over `period`)
- `granularity` (`auto` | `hour` | `day` | `week` | `month`, default `auto`)
  - `auto`: span ≤ 2d → hour, ≤ 62d → day, ≤ 400d → week, else month

Add new routes:

- `GET /analytics/toner-breakdown` — time-series cost per toner color. Response: `[{bucket: "2026-04-20", paper: 12.5, k: 8.1, c: 4.2, m: 3.9, y: 4.0, gld_1: 0.5, ...}]`.
- `GET /analytics/paper-breakdown` — cost grouped by paper type (donut-ready): `[{paper_type: "Plain 80", cost: 120.5, pages: 3400}, ...]`.
- `GET /analytics/top-jobs?limit=20&order=cost|pages|waste` — ranked job list with all per-color costs.

All accept `printer_id` filter.

Backward compatibility: existing `period` param stays; if both `period` and explicit dates are passed, explicit dates win.

---

## 7. Dashboard UI

Replace the four-button period switcher with a **`DateRangePicker`** (presets + custom range) that writes `{start, end}` to the query state. Keep the presets "Today / 7d / 30d / 90d / 1y" as quick-picks inside the picker.

### 7.1 Top KPI row (existing, plus)

- Total cost · Cost per page · Paper cost · Toner cost · Waste cost · Total pages · Jobs
- Small delta vs previous equal-length window (e.g. "+12.3% vs previous 30d")

### 7.2 Cost over time — stacked area chart

X axis = time bucket; Y axis = cost stacked by paper + each toner color. Uses `/analytics/toner-breakdown`. Colors pulled from a palette map (see §7.6). Recharts `<AreaChart stackId>`.

### 7.3 Paper vs Toner — side-by-side

Two panels:

- **Paper breakdown** — colorful 3D-style donut chart per paper type, driven by `/analytics/paper-breakdown`. Implementation: Recharts `PieChart` with custom label renderer, active-sector zoom on hover, radial gradient fills, and a drop-shadow to give a quasi-3D feel (Recharts doesn't render true 3D; a `PieChart` with gradient + shadow looks colorful and remains readable). Alternate view toggle: grouped bar chart (paper type × cost). User picks per session.
- **Toner breakdown** — horizontal bar chart per toner color (easier to read for 8+ specialty toners than a donut). Colors from the palette map.

### 7.4 Top jobs table

Rows: job_id · job_name · paper_type · pages · paper cost · toner cost · total · waste flag. Click opens a side drawer (`JobDetailDrawer`) with:

- Stacked bar: per-color cost
- Raster coverage % per color (actual vs estimation)
- Cartridge source (which replacement log each color was priced from)

### 7.5 Toner consumption panel (new)

One card per active toner on the selected printer:

- Current cartridge (from latest replacement log)
- Pages printed since replacement
- Cumulative coverage % × pages / (ref_cov_pct × rated_yield) → "X% of rated yield consumed"
- Estimated remaining pages at current burn rate
- Spend to date on this cartridge
- Warning pill when > 80% consumed

### 7.6 Color palette

Define `frontend/src/lib/tonerPalette.ts`:

```ts
export const TONER_COLORS: Record<string, string> = {
  paper:  "#60a5fa",   // blue-400
  k:      "#1f2937",   // slate-800
  c:      "#06b6d4",   // cyan-500
  m:      "#ec4899",   // pink-500
  y:      "#facc15",   // yellow-400
  gld_1:  "#d4af37",   // gold
  slv_1:  "#c0c0c0",   // silver
  clr_1:  "#a5f3fc",   // cyan-200 (clear-ish)
  wht_1:  "#f8fafc",   // slate-50 w/ border
  cr_1:   "#fb923c",   // orange-400 (texture)
  p_1:    "#f472b6",   // pink-400
  pa_1:   "#a78bfa",   // violet-400
  gld_6:  "#b8860b",   // darkgoldenrod
  slv_6:  "#9ca3af",   // slate-400
  wht_6:  "#e2e8f0",   // slate-200 w/ border
  p_6:    "#e879f9",   // fuchsia-400
};
```

All charts consume this map. Gradients (for the 3D-style donut) use `<defs><linearGradient>` with lightened/darkened stops per color.

---

## 8. Files touched

**Backend**
- `backend/app/models/toner.py` — add `reference_coverage_pct`, `cartridge_reference_coverage_pct`
- `backend/app/models/upload.py` — add `computed_toner_cost_breakdown`, `cost_computed_at`, `cost_computation_source`
- `backend/alembic/versions/005_*.py` — new migration
- `backend/app/services/cost_calc.py` — **new** module (paper match + toner cost + per-color breakdown)
- `backend/app/routers/print_jobs.py` — call `compute_job_cost()` during upload; add `/recompute-costs`
- `backend/app/routers/analytics.py` — extend existing routes; add `toner-breakdown`, `paper-breakdown`, `top-jobs`
- `backend/app/routers/cost_config.py` — add `GET /printers/{id}/paper-suggestions`; emit recompute hint on paper/toner edits
- `backend/app/routers/toner_replacements.py` — auto-trigger recompute after new log; confirm datetime-local capture

**Frontend**
- `frontend/src/components/ui/DateRangePicker.tsx` — **new**
- `frontend/src/lib/tonerPalette.ts` — **new**
- `frontend/src/pages/dashboard/DashboardPage.tsx` — rework period control, add new panels
- `frontend/src/components/charts/StackedCostAreaChart.tsx` — **new**
- `frontend/src/components/charts/PaperDonut3D.tsx` — **new** (gradient + shadow donut)
- `frontend/src/components/charts/TonerBreakdownBar.tsx` — **new**
- `frontend/src/components/charts/TonerConsumptionCard.tsx` — **new**
- `frontend/src/components/charts/JobDetailDrawer.tsx` — **new**
- `frontend/src/pages/printers/PaperAddPage.tsx` (or equivalent) — add "Suggest from CSV" dropdown
- `frontend/src/pages/printers/TonerEditPage.tsx` — expose `reference_coverage_pct`
- `frontend/src/pages/printers/ColumnMappingPage.tsx` — help tooltip explaining paper fields

---

## 9. Testing

- Unit: `cost_calc.py` — coverage fallback, pricing-window selection, specialty-toner pages mapping, edge cases (zero coverage, no replacement log, null matched_paper).
- Integration: upload a CSV → verify computed columns; edit a toner price → run recompute → verify changes.
- Frontend: `DashboardPage` renders with date-range changes; empty state; loading skeletons.

---

## 10. Migration order

1. Alembic migration adds new columns with defaults.
2. Deploy backend with calc engine + recompute endpoint (no-op on empty columns).
3. Run a one-time admin script `POST /printers/{id}/recompute-costs` on each printer.
4. Deploy frontend changes.

No downtime required; columns default to safe values and the UI degrades gracefully while costs are `0`.
