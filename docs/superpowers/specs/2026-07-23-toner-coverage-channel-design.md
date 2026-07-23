# Explicit Toner → Coverage-Column Mapping

**Date:** 2026-07-23
**Status:** Approved (design)

## Problem

When adding a toner, the user picks a color *name* — "Black", "Cyan", "Gold" —
in the Add Toner form (`frontend/src/pages/printers/PrinterDetailPage.tsx`,
`STANDARD_COLORS`). The cost engine (`backend/app/services/cost_calc.py`,
`_COLOR_MAP`) keys on short channel codes — `K`, `C`, `M`, `Y`, `GLD`, `SLV`, …
— to decide which database coverage column feeds the raster-coverage cost
formula.

`_normalize_color("Black")` returns `"BLACK"`, which is not a `_COLOR_MAP` key,
so the toner is silently skipped and contributes **₹0**. Standard CMYK toners
and specialty toners entered by friendly name (e.g. "Gold" vs. the aliased
"GLD #1") all hit this wall. Unit tests pass only because they use the raw
codes (`toner_color="K"`), which never come from the real UI.

The cost formula itself is correct (`cost_calc.py`):

```
cost = (coverage / reference_coverage_pct) * (price_per_unit / rated_yield_pages) * pages
```

The defect is that the color chosen in the UI never reaches the formula because
there is no reliable link between a toner and its coverage column.

## Goal

Give the user an explicit, required selector that marks which database coverage
column each toner drives, filtered to the channels actually mapped for that
printer. This delivers explicit control and structurally prevents the silent
₹0 result.

## Design

### 1. Data model

Add one column to the `toners` table (`backend/app/models/toner.py`):

- `coverage_channel: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)`
  — stores a `_COLOR_MAP` key: one of
  `K, C, M, Y, GLD, SLV, CLR, WHT, CR, P, PA, GLD_6, SLV_6, WHT_6, P_6`.

Nullable at the DB level so backfill and the fallback path stay safe, but
**required by the API and the UI** for new/edited toners.

Add a uniqueness constraint `uq_toners_printer_channel` on
`(printer_id, coverage_channel)` — one toner per channel per printer. NULLs are
permitted (Postgres allows multiple NULLs under a unique constraint), so
un-backfilled legacy rows don't violate it.

The existing `(printer_id, toner_color)` unique constraint stays. `toner_color`
becomes a free-text **display label**; `coverage_channel` is the source of
truth for cost calculation.

### 2. Migration + backfill

New Alembic migration (next sequential version after `005_r14_cost_fields.py`):

1. Add the `coverage_channel` column.
2. Backfill existing rows: normalize each row's current `toner_color` to a
   channel key using this lookup (case-insensitive):

   | toner_color | channel |
   |-------------|---------|
   | Black, K | K |
   | Cyan, C | C |
   | Magenta, M | M |
   | Yellow, Y | Y |
   | Gold, GLD, GLD #1 | GLD |
   | Silver, SLV, SLV #1 | SLV |
   | Clear, CLR, CLR #1 | CLR |
   | White, WHT, WHT #1 | WHT |
   | Texture, CR, CR #1 | CR |
   | Pink, P, P #1 | P |
   | PA, PA #1 | PA |
   | GLD #6 | GLD_6 |
   | SLV #6 | SLV_6 |
   | WHT #6 | WHT_6 |
   | P #6 | P_6 |

   Any `toner_color` that does not match stays `NULL`. The fallback path (§3)
   still computes its cost, and the UI (§5) flags it as needing attention.
3. Add the `uq_toners_printer_channel` unique constraint.

Downgrade drops the constraint and the column.

### 3. Backend cost calculation

In `cost_calc.py`, `compute_job_cost` resolves the channel per toner as:

```
color_key = t.coverage_channel or _normalize_color(t.toner_color)
```

Everything downstream — the `_COLOR_MAP` lookup, coverage/pages column
selection, pricing, and the formula — is unchanged. Keeping the
`_normalize_color` fallback preserves current behavior for un-backfilled rows
and the existing unit tests (which pass `toner_color="K"`).

### 4. API

In `backend/app/routers/printers.py`:

- The toner create/update request schema (`TonerCreate`, around
  `printers.py:51`) gains `coverage_channel: str`, **required on create**.
- Server-side validation on create/update:
  - reject if `coverage_channel` is not a valid `_COLOR_MAP` key
    (HTTP 422 / 400 with a clear message);
  - reject if the channel's coverage column is not mapped for that printer
    (load the printer's `column_mapping`, check the coverage field is present).
- Toner GET responses (around `printers.py:371`) include `coverage_channel`.

Expose the `_COLOR_MAP` key set (and each key's coverage column name) from a
single source so the validator and any serialization stay consistent with the
cost engine. Reuse `_COLOR_MAP` rather than duplicating the list.

### 5. Frontend

In `PrinterDetailPage.tsx`:

- Add a `CHANNEL_CATALOG` constant mirroring `_COLOR_MAP`: channel key →
  `{ coverageField, label }`, e.g. `K → { coverageField: 'coverage_k',
  label: 'Black (K)' }`, `GLD → { coverageField: 'coverage_gld_1',
  label: 'Gold #1' }`, etc.
- The Add Toner and Edit Toner forms gain a **required** "Coverage column"
  `<select>`. Options are the catalog entries whose `coverageField` is present
  in this printer's `columnMapping` (the rule agreed: a channel is "mapped for
  this printer" when its coverage column appears in the mapping).
- The Add/Save button is disabled until a coverage channel is selected.
- In the toner list, any toner with an empty `coverage_channel` (legacy rows
  the backfill couldn't resolve) shows a "needs attention" indicator prompting
  the user to edit and set the column.

`toner_color` remains a free label the user can type; the coverage channel is
the functional link.

### 6. Verification

- `backend/tests/unit/test_cost_calc.py`:
  - a toner with `toner_color="Black"` and `coverage_channel="K"` computes a
    non-zero K cost (reproduces and fixes the exact bug);
  - `coverage_channel` takes precedence over `toner_color` when both are set;
  - fallback: `coverage_channel=None`, `toner_color="K"` still computes
    (existing behavior preserved).
- Migration backfill: unit/integration check that sample rows
  (`toner_color` "Black", "Gold", "K") map to `K`, `GLD`, `K`.
- API: create toner without `coverage_channel` → rejected; with an unmapped
  channel → rejected.
- Manual: add a Black toner via the UI selecting the Black (K) column, run a
  cost recompute, confirm the dashboard toner cost for K is non-zero.

## Out of scope

- No change to the raster-coverage cost formula.
- No change to column mapping or CSV ingest.
- No bulk re-mapping UI beyond editing individual toners.
