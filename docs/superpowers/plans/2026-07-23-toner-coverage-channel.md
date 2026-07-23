# Toner → Coverage-Column Mapping Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let users explicitly mark which raster-coverage database column each toner drives, so per-color toner cost stops silently computing as ₹0.

**Architecture:** Add a `coverage_channel` key to each toner (mirrors the channel keys in `cost_calc._COLOR_MAP`). A new shared helper module owns the channel catalog, legacy-name backfill, and validation. The cost engine uses the stored channel (falling back to today's name normalization). The API requires and validates it; the UI presents a required dropdown filtered to channels mapped for the printer.

**Tech Stack:** Python 3 / FastAPI / SQLAlchemy / Alembic / pytest (backend); React + TypeScript + react-query (frontend).

## Global Constraints

- Channel keys are exactly: `K, C, M, Y, GLD, SLV, CLR, WHT, CR, P, PA, GLD_6, SLV_6, WHT_6, P_6` (must equal `set(cost_calc._COLOR_MAP)`).
- `coverage_channel` is DB-nullable but API/UI-required for create and edit.
- `toner_color` remains a free-text display label; `coverage_channel` is the source of truth for cost.
- Never change the cost formula: `cost = (coverage / reference_coverage_pct) * (price_per_unit / rated_yield_pages) * pages`.
- Backfill unmatched `toner_color` values to `NULL` (fallback covers them); do not guess.
- Run backend tests from `backend/`: `python -m pytest`.

---

## File Structure

- Create: `backend/app/services/toner_channels.py` — channel catalog, backfill, validation (pure functions).
- Create: `backend/tests/unit/test_toner_channels.py` — tests for the helpers.
- Create: `backend/alembic/versions/006_r15_toner_coverage_channel.py` — column + backfill + constraint.
- Modify: `backend/app/models/toner.py` — add column + unique constraint.
- Modify: `backend/app/services/cost_calc.py` — resolve channel from `coverage_channel` with fallback.
- Modify: `backend/tests/unit/test_cost_calc.py` — add bug-repro + precedence + fallback tests.
- Modify: `backend/app/routers/printers.py` — schema field, validation, serialization.
- Create: `backend/tests/unit/test_toner_channel_validation.py` — validator behavior.
- Modify: `frontend/src/pages/printers/PrinterDetailPage.tsx` — catalog, required selectors, list flag.

---

## Task 1: Channel catalog + backfill + validation helpers

**Files:**
- Create: `backend/app/services/toner_channels.py`
- Test: `backend/tests/unit/test_toner_channels.py`

**Interfaces:**
- Produces:
  - `COVERAGE_COLUMN_BY_CHANNEL: dict[str, str]` — channel key → `print_jobs` coverage column name.
  - `CHANNEL_KEYS: frozenset[str]`
  - `backfill_channel(toner_color: str) -> str | None`
  - `validate_coverage_channel(channel: str, column_mapping: dict | None) -> str | None` (returns error message or `None`)

- [ ] **Step 1: Write the failing test**

Create `backend/tests/unit/test_toner_channels.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/unit/test_toner_channels.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.services.toner_channels'`

- [ ] **Step 3: Write minimal implementation**

Create `backend/app/services/toner_channels.py`:

```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/unit/test_toner_channels.py -v`
Expected: PASS (all 7 tests)

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/toner_channels.py backend/tests/unit/test_toner_channels.py
git commit -m "feat(toner): add coverage-channel catalog, backfill, and validation helpers"
```

---

## Task 2: Model column + Alembic migration with backfill

**Files:**
- Modify: `backend/app/models/toner.py:32-58`
- Create: `backend/alembic/versions/006_r15_toner_coverage_channel.py`

**Interfaces:**
- Consumes: `app.services.toner_channels.backfill_channel` (Task 1).
- Produces: `Toner.coverage_channel` attribute; DB column `toners.coverage_channel`; unique constraint `uq_toners_printer_channel`.

- [ ] **Step 1: Add the model column and constraint**

In `backend/app/models/toner.py`, extend `__table_args__` (currently at lines 34-36) to add the channel constraint:

```python
    __table_args__ = (
        UniqueConstraint("printer_id", "toner_color", name="uq_toners_printer_color"),
        UniqueConstraint("printer_id", "coverage_channel", name="uq_toners_printer_channel"),
    )
```

And add the column after `toner_color` (currently line 44):

```python
    coverage_channel: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
```

(`Optional` and `String` are already imported in this file.)

- [ ] **Step 2: Write the migration**

Create `backend/alembic/versions/006_r15_toner_coverage_channel.py`:

```python
"""Rev 1.5 — explicit coverage_channel on toners.

Revision ID: 006
Revises: 005
Create Date: 2026-07-23
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

from app.services.toner_channels import backfill_channel

revision = "006"
down_revision = "005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "toners",
        sa.Column("coverage_channel", sa.String(10), nullable=True),
    )
    conn = op.get_bind()
    rows = conn.execute(sa.text("SELECT id, toner_color FROM toners")).fetchall()
    for row_id, toner_color in rows:
        channel = backfill_channel(toner_color)
        if channel:
            conn.execute(
                sa.text("UPDATE toners SET coverage_channel = :c WHERE id = :i"),
                {"c": channel, "i": row_id},
            )
    op.create_unique_constraint(
        "uq_toners_printer_channel", "toners", ["printer_id", "coverage_channel"]
    )


def downgrade() -> None:
    op.drop_constraint("uq_toners_printer_channel", "toners", type_="unique")
    op.drop_column("toners", "coverage_channel")
```

- [ ] **Step 3: Apply the migration**

Run: `cd backend && alembic upgrade head`
Expected: completes without error; `alembic current` shows `006`.

- [ ] **Step 4: Verify the column and backfill**

Run: `cd backend && python -c "from app.models.toner import Toner; print('coverage_channel' in Toner.__table__.columns)"`
Expected: `True`

If any toners already exist, spot-check in a DB client that a "Black" toner now has `coverage_channel = 'K'`.

- [ ] **Step 5: Commit**

```bash
git add backend/app/models/toner.py backend/alembic/versions/006_r15_toner_coverage_channel.py
git commit -m "feat(toner): add coverage_channel column + backfill migration"
```

---

## Task 3: Cost engine uses coverage_channel with fallback

**Files:**
- Modify: `backend/app/services/cost_calc.py:181-186`
- Test: `backend/tests/unit/test_cost_calc.py`

**Interfaces:**
- Consumes: `Toner.coverage_channel` (Task 2); existing `_COLOR_MAP`, `_normalize_color`.

- [ ] **Step 1: Write the failing tests**

Append to `backend/tests/unit/test_cost_calc.py` (the `_toner` helper builds a `SimpleNamespace`; add `coverage_channel` via a small wrapper so existing calls stay valid):

```python
def _toner_ch(color, channel, **kw):
    t = _toner(color, **kw)
    t.coverage_channel = channel
    return t


def test_coverage_channel_drives_cost_when_name_mismatches():
    # Real-world bug: UI stores friendly name "Black", not code "K".
    j = _job()
    toners = [_toner_ch("Black", "K")]
    result = compute_job_cost(j, toners=toners, matched_paper=_paper())
    assert result["breakdown"]["k"] > 0


def test_coverage_channel_takes_precedence_over_name():
    j = _job()
    # name says Yellow but channel says K -> should compute the K column
    toners = [_toner_ch("Yellow", "K")]
    result = compute_job_cost(j, toners=toners, matched_paper=_paper())
    assert result["breakdown"]["k"] > 0


def test_falls_back_to_name_when_channel_absent():
    # Legacy row with no channel but a valid code name still computes.
    j = _job()
    toners = [_toner("K")]  # no coverage_channel attribute set
    result = compute_job_cost(j, toners=toners, matched_paper=_paper())
    assert result["breakdown"]["k"] > 0
```

- [ ] **Step 2: Run tests to verify the new ones fail**

Run: `cd backend && python -m pytest tests/unit/test_cost_calc.py -v -k "coverage_channel or falls_back"`
Expected: `test_coverage_channel_drives_cost_when_name_mismatches` and `test_coverage_channel_takes_precedence_over_name` FAIL (breakdown["k"] == 0); `test_falls_back_to_name_when_channel_absent` PASSES already.

- [ ] **Step 3: Implement channel resolution**

In `backend/app/services/cost_calc.py`, inside `compute_job_cost`, replace the loop head (currently lines 181-184):

```python
    for t in toners:
        color_key = _normalize_color(t.toner_color)
        if color_key not in _COLOR_MAP:
            continue
```

with:

```python
    for t in toners:
        color_key = getattr(t, "coverage_channel", None) or _normalize_color(t.toner_color)
        if color_key not in _COLOR_MAP:
            continue
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/unit/test_cost_calc.py -v`
Expected: PASS (all, including the three new ones)

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/cost_calc.py backend/tests/unit/test_cost_calc.py
git commit -m "fix(cost): use toner.coverage_channel with name fallback so costs stop being zero"
```

---

## Task 4: API — require, validate, and serialize coverage_channel

**Files:**
- Modify: `backend/app/routers/printers.py:50-56` (schema), `279-311` (create/update), `367-378` (`_toner_out`)
- Test: `backend/tests/unit/test_toner_channel_validation.py`

**Interfaces:**
- Consumes: `app.services.toner_channels.validate_coverage_channel` (Task 1).
- Produces: `coverage_channel` accepted on create/update and returned in toner responses.

- [ ] **Step 1: Write the failing test**

Create `backend/tests/unit/test_toner_channel_validation.py` (unit-tests the validator wiring used by the router — no HTTP/auth needed):

```python
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
```

- [ ] **Step 2: Run test to verify it passes** (validator already exists from Task 1)

Run: `cd backend && python -m pytest tests/unit/test_toner_channel_validation.py -v`
Expected: PASS. (This test locks the validator contract the router depends on.)

- [ ] **Step 3: Add the schema field**

In `backend/app/routers/printers.py`, add to `TonerCreate` (after `toner_color`, line 51):

```python
    coverage_channel: str
```

- [ ] **Step 4: Validate and persist on create**

Add the import near the top of `printers.py` (with the other `app.services` / model imports):

```python
from app.services.toner_channels import validate_coverage_channel
```

In `create_toner` (line 280), capture the printer and validate before building the row:

```python
async def create_toner(printer_id: int, body: TonerCreate, current_user: OwnerUser, db: Session = Depends(get_db)):
    p = _get_printer_or_404(db, printer_id, current_user.id)
    err = validate_coverage_channel(body.coverage_channel, p.column_mapping)
    if err:
        raise HTTPException(status_code=422, detail=err)
    t = Toner(
        printer_id=printer_id,
        toner_color=body.toner_color,
        coverage_channel=body.coverage_channel,
        toner_type=TonerType(body.toner_type),
        price_per_unit=body.price_per_unit,
        rated_yield_pages=body.rated_yield_pages,
        reference_coverage_pct=Decimal(str(body.reference_coverage_pct)),
        currency=body.currency,
    )
    db.add(t)
    db.commit()
    db.refresh(t)
    return {"data": _toner_out(t), "message": "Toner created"}
```

- [ ] **Step 5: Validate and persist on update**

In `update_toner` (line 298), capture the printer, validate, and set the field:

```python
async def update_toner(printer_id: int, toner_id: int, body: TonerCreate, current_user: OwnerUser, db: Session = Depends(get_db)):
    p = _get_printer_or_404(db, printer_id, current_user.id)
    t = db.query(Toner).filter(Toner.id == toner_id, Toner.printer_id == printer_id).first()
    if not t:
        raise HTTPException(status_code=404, detail="Toner not found")
    err = validate_coverage_channel(body.coverage_channel, p.column_mapping)
    if err:
        raise HTTPException(status_code=422, detail=err)
    t.toner_color = body.toner_color
    t.coverage_channel = body.coverage_channel
    t.toner_type = TonerType(body.toner_type)
    t.price_per_unit = Decimal(str(body.price_per_unit))
    t.rated_yield_pages = body.rated_yield_pages
    t.reference_coverage_pct = Decimal(str(body.reference_coverage_pct))
    t.currency = body.currency
    db.commit()
    db.refresh(t)
    return {"data": _toner_out(t), "message": "Toner updated", "recompute_hint": True}
```

- [ ] **Step 6: Serialize the field**

In `_toner_out` (line 367), add after `"toner_color"`:

```python
        "coverage_channel": t.coverage_channel,
```

- [ ] **Step 7: Run the backend suite**

Run: `cd backend && python -m pytest -v`
Expected: PASS (no regressions).

- [ ] **Step 8: Commit**

```bash
git add backend/app/routers/printers.py backend/tests/unit/test_toner_channel_validation.py
git commit -m "feat(api): require and validate toner coverage_channel; return it in responses"
```

---

## Task 5: Frontend — required coverage-column selector + list flag

**Files:**
- Modify: `frontend/src/pages/printers/PrinterDetailPage.tsx` (top constants ~line 31; `TonerManagement` state line 47; add form ~155-199; add mutation 71-85; edit modal 307-344; list 274-301)

**Interfaces:**
- Consumes: toner API `coverage_channel` field (Task 4); printer `column_mapping` prop.

- [ ] **Step 1: Add the channel catalog constant**

In `PrinterDetailPage.tsx`, after the `FIELD_TO_TONER` map (around line 31), add:

```typescript
// Channel key -> its raster-coverage column + display label. Mirrors backend _COLOR_MAP.
const CHANNEL_CATALOG: Record<string, { coverageField: string; label: string }> = {
  K:     { coverageField: 'coverage_k',      label: 'Black (K)' },
  C:     { coverageField: 'coverage_c',      label: 'Cyan (C)' },
  M:     { coverageField: 'coverage_m',      label: 'Magenta (M)' },
  Y:     { coverageField: 'coverage_y',      label: 'Yellow (Y)' },
  GLD:   { coverageField: 'coverage_gld_1',  label: 'Gold #1' },
  SLV:   { coverageField: 'coverage_slv_1',  label: 'Silver #1' },
  CLR:   { coverageField: 'coverage_clr_1',  label: 'Clear #1' },
  WHT:   { coverageField: 'coverage_wht_1',  label: 'White #1' },
  CR:    { coverageField: 'coverage_cr_1',   label: 'Texture (CR #1)' },
  P:     { coverageField: 'coverage_p_1',    label: 'Pink #1' },
  PA:    { coverageField: 'coverage_pa_1',   label: 'PA #1' },
  GLD_6: { coverageField: 'coverage_gld_6',  label: 'Gold #6' },
  SLV_6: { coverageField: 'coverage_slv_6',  label: 'Silver #6' },
  WHT_6: { coverageField: 'coverage_wht_6',  label: 'White #6' },
  P_6:   { coverageField: 'coverage_p_6',    label: 'Pink #6' },
};
```

- [ ] **Step 2: Derive the printer's available channels + add channel to form state**

Inside `TonerManagement`, add after the `suggestedColors` block (around line 65):

```typescript
  // Channels whose coverage column is mapped for this printer
  const availableChannels = Object.entries(CHANNEL_CATALOG)
    .filter(([, v]) => v.coverageField in (columnMapping ?? {}))
    .map(([key, v]) => ({ key, label: v.label }));
```

Update the `form` initial state (line 47) to include `coverage_channel`:

```typescript
  const [form, setForm] = useState({ toner_color: '', coverage_channel: '', toner_type: 'standard', price_per_unit: '', rated_yield_pages: '', reference_coverage_pct: '5.00', currency: 'INR' });
```

Update the `editForm` initial state (line 49) to include it:

```typescript
  const [editForm, setEditForm] = useState({ coverage_channel: '', price_per_unit: '', rated_yield_pages: '', reference_coverage_pct: '5.00', currency: 'INR' });
```

- [ ] **Step 3: Send coverage_channel in both mutations + reset**

In `addToner` mutation body (line 72-79), add `coverage_channel: form.coverage_channel,`. In its `onSuccess` reset (line 82), add `coverage_channel: '',` to the reset object.

In `updateToner` mutation body (line 93-99), add `coverage_channel: editForm.coverage_channel,`.

- [ ] **Step 4: Add the required selector to the Add form**

In the Add Toner form, immediately after the Color field block (after line 199, before the Type field at line 200), add:

```tsx
            <div className="space-y-1 col-span-2">
              <Label>Coverage Column *</Label>
              <select
                className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm"
                value={form.coverage_channel}
                onChange={e => setForm(p => ({ ...p, coverage_channel: e.target.value }))}
              >
                <option value="">Select coverage column...</option>
                {availableChannels.map(c => (
                  <option key={c.key} value={c.key}>{c.label}</option>
                ))}
              </select>
              {availableChannels.length === 0 && (
                <p className="text-xs text-muted-foreground mt-1">
                  No raster-coverage columns are mapped for this printer. Map them in{' '}
                  <a href={`/printers/${printerId}/mapping`} className="text-primary hover:underline">Column Mapping</a> first.
                </p>
              )}
            </div>
```

- [ ] **Step 5: Require the channel before enabling Add**

In the Add button `disabled` expression (line 243), append `|| !form.coverage_channel`:

```tsx
              disabled={!form.toner_color || form.toner_color === '__custom__' || !form.coverage_channel || !form.price_per_unit || !form.rated_yield_pages || addToner.isPending}
```

- [ ] **Step 6: Initialize + require the channel in the Edit modal**

In the edit-open handler (line 285-287), include the channel when seeding `editForm`:

```tsx
                          setEditForm({ coverage_channel: t.coverage_channel ?? '', price_per_unit: String(t.price_per_unit), rated_yield_pages: String(t.rated_yield_pages), reference_coverage_pct: String(t.reference_coverage_pct ?? '5.00'), currency: t.currency });
```

In the edit modal body, add a selector before the Price field (before line 313):

```tsx
              <div className="space-y-1">
                <Label>Coverage Column *</Label>
                <select
                  className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm"
                  value={editForm.coverage_channel}
                  onChange={e => setEditForm(p => ({ ...p, coverage_channel: e.target.value }))}
                >
                  <option value="">Select coverage column...</option>
                  {availableChannels.map(c => (
                    <option key={c.key} value={c.key}>{c.label}</option>
                  ))}
                </select>
              </div>
```

Disable the Save button until a channel is set (line 340), add `disabled={updateToner.isPending || !editForm.coverage_channel}`:

```tsx
              <Button size="sm" onClick={() => updateToner.mutate()} disabled={updateToner.isPending || !editForm.coverage_channel} isLoading={updateToner.isPending}>Save</Button>
```

- [ ] **Step 7: Flag legacy toners with no channel in the list**

In the toner list row, change the Color cell (line 277) to surface a "needs attention" hint when `coverage_channel` is empty:

```tsx
                  <td className="px-4 py-2.5 font-medium">
                    {t.toner_color}
                    {!t.coverage_channel && (
                      <span className="ml-2 rounded bg-amber-100 px-1.5 py-0.5 text-[10px] font-normal text-amber-700">
                        set coverage column
                      </span>
                    )}
                  </td>
```

- [ ] **Step 8: Verify the build and behavior**

Run: `cd frontend && npm run build`
Expected: type-check + build succeed.

Manual check (dev server): open a printer with mapped coverage columns → Add Toner shows the required "Coverage Column" dropdown listing only mapped channels; Add is disabled until one is chosen; a legacy toner without a channel shows the amber "set coverage column" badge.

- [ ] **Step 9: Commit**

```bash
git add frontend/src/pages/printers/PrinterDetailPage.tsx
git commit -m "feat(ui): add required coverage-column selector to toner add/edit + legacy flag"
```

---

## Task 6: End-to-end verification

- [ ] **Step 1: Full backend suite**

Run: `cd backend && python -m pytest -v`
Expected: PASS.

- [ ] **Step 2: Manual cost check**

With the app running: add a Black toner selecting the **Black (K)** coverage column, trigger a cost recompute for the printer, and confirm the dashboard toner cost for K is now non-zero (previously ₹0). Record the before/after in the PR description.

---

## Self-Review

- **Spec coverage:** §1 data model → Task 2; §2 migration/backfill → Tasks 1-2; §3 cost calc → Task 3; §4 API → Task 4; §5 frontend → Task 5; §6 verification → Tasks 3-6. All sections covered.
- **Placeholders:** none — every code step shows full code.
- **Type consistency:** channel keys identical across `toner_channels.py`, `CHANNEL_CATALOG`, and `_COLOR_MAP` (Task 1 test enforces equality); `coverage_channel` field name consistent across model, migration, API, and frontend.
