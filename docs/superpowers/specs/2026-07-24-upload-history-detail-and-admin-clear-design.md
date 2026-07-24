# Upload History: Error Detail View + Admin Batch Clear

**Date:** 2026-07-24
**Status:** Implemented (2026-07-24), scope reduced from the original draft

> **Scope change.** The original draft proposed an admin-page section with a
> per-printer bulk clear. That was cut in favour of deleting **individual** history
> rows directly from the printer's Upload History list, owner-gated. §3 and §5 below
> reflect what was built; the bulk-clear and admin-summary endpoints were not.

## Problem

Two gaps in upload history, surfaced while debugging the n8n Drive ingest:

1. **Errors are invisible.** `UploadBatch.skipped_details` (JSONB) already records
   `{row_number, reason}` for every skipped row, but `GET /uploads` never returns
   it. When an import reports `0/1 rows`, there is no way to find out why from the
   UI.

2. **History can't be cleaned up.** A misconfigured n8n workflow created three
   `upload_batches` rows per file (see §7). There is no admin path to remove junk
   batch rows without also destroying imported print jobs.

## Scope

In scope:

- Read-only drawer showing a batch's skipped-row detail.
- Owner-only, per-printer clearing of `upload_batches` rows.

Out of scope:

- Cross-printer bulk clear, filtering, or row-level selection.
- Any change to the existing `DELETE /uploads/clear` endpoint (see §6).
- Fixing the n8n workflow itself (tracked separately, see §7).

## 1. Data model

No migration. Every field needed already exists on `UploadBatch`:
`source`, `filename`, `uploaded_at`, `rows_total`, `rows_imported`,
`rows_skipped`, `skipped_details`, `status`.

`skipped_details` is written by `csv_import_service.py:410` and `:422` as a list of
`{"row_number": int, "reason": str}`.

## 2. Backend — batch detail

New route in `backend/app/routers/print_jobs.py`:

```
GET /api/v1/printers/{printer_id}/uploads/{batch_id}
```

- Auth: `CurrentUser`, via the existing `_get_printer_or_403(db, printer_id, current_user.id)`,
  matching every other route in this router.
- 404 if the batch does not exist **or** belongs to a different printer. This check
  must be written explicitly in the new endpoint as
  `filter(UploadBatch.id == batch_id, UploadBatch.printer_id == printer_id)` — it
  cannot be delegated to the helper (see note below).

> **Pre-existing issue, not introduced here.** Despite its name,
> `_get_printer_or_403` (`print_jobs.py:35-39`) accepts `owner_id` but never
> references it — it only raises 404 when the printer is missing. There is
> currently no per-user ownership isolation on any printer-scoped route. This spec
> follows the existing pattern rather than silently changing the auth model, but the
> gap is real and worth its own ticket. It also means the batch/printer match in §2
> is the only thing preventing one printer's batch detail being read through
> another's path.
- Returns the full batch record including `source` and `skipped_details`.

```json
{
  "data": {
    "id": 198,
    "filename": "sample.csv",
    "source": "automated",
    "uploaded_at": "2026-07-24T08:32:36+00:00",
    "status": "completed",
    "rows_total": 1,
    "rows_imported": 0,
    "rows_skipped": 1,
    "skipped_details": [{ "row_number": 2, "reason": "Duplicate job" }]
  },
  "message": "ok"
}
```

**Route ordering:** declare this after the existing `GET ""`. The sibling routes
(`/import`, `/preview`, `/recompute-costs` are POST; `/clear` is DELETE) do not
collide with a GET, but the path must be declared as `{batch_id:int}` so a future
literal GET segment cannot be swallowed by it.

`skipped_details` is deliberately **not** added to the list endpoint — 20 batches
of a large failed import would make the list response very heavy. The list gains
only `source`, which the drawer header and the row badge need.

## 3. Backend — delete one history row

One new route in `backend/app/routers/print_jobs.py`, alongside the detail endpoint:

```
DELETE /api/v1/printers/{printer_id}/uploads/{batch_id}
```

- Auth: `OwnerUser`. This is the only route in this router that requires owner —
  every other one takes `CurrentUser` — so a `print_person` gets 403.
- 404 on a missing batch, or one belonging to a different printer.
- Deletes exactly one `upload_batches` row. Print jobs are kept.

### The delete must be a bulk query delete

This is the critical implementation detail:

```python
deleted = (
    db.query(UploadBatch)
    .filter(UploadBatch.printer_id == printer_id)
    .delete(synchronize_session=False)
)
db.commit()
```

`UploadBatch.print_jobs` declares `cascade="all, delete-orphan"`
(`models/upload.py:86-90`), while the DB-level FK on `print_jobs.upload_batch_id`
is `ondelete="SET NULL"` (`models/upload.py:110-114`). These disagree on purpose-built
behaviour:

- A **bulk query delete** emits `DELETE FROM upload_batches WHERE printer_id = ...`,
  and Postgres applies `SET NULL`. Print jobs survive, orphaned but intact.
- An **ORM delete** (`db.delete(batch)` in a loop, or loading then deleting) triggers
  the `delete-orphan` cascade and **deletes every print job in the batch**.

Only the first is acceptable. Response:

```json
{ "data": { "batches_deleted": 42, "jobs_preserved": 1298 }, "message": "..." }
```

`jobs_preserved` is counted before the delete and returned so the caller gets
positive confirmation that job data was retained.

## 4. Frontend — error drawer

New `frontend/src/components/printers/UploadBatchDrawer.tsx`, following the
existing `components/charts/JobDetailDrawer.tsx` pattern.

Props: `{ printerId: string; batchId: number | null; onClose: () => void }`.
Fetches via react-query keyed `['upload-batch', printerId, batchId]`, enabled only
when `batchId !== null`.

Layout:

- Header — filename, `source` badge, formatted `uploaded_at`, status pill.
- Summary line — `{rows_total} total · {rows_imported} imported · {rows_skipped} skipped`.
- Body — skipped rows **grouped by reason**, each group showing its count and
  collapsed by default. Grouping matters because a bad import typically produces
  one reason repeated hundreds of times; an ungrouped list is unreadable.
- Each group lists its row numbers, capped at 100 with a `+N more` indicator.
- Empty state when `skipped_details` is empty: "All rows imported successfully."

In `PrinterDetailPage.tsx`, the upload-history rows (currently `<div>`, lines
788-810) become keyboard-focusable buttons that set `selectedBatchId`. Visual
design of the list is otherwise unchanged.

## 5. Frontend — per-row delete

No admin page changes. The delete lives in the existing Upload History list on
`PrinterDetailPage.tsx`: each row gets a trash button, rendered only when
`hasRole('owner')` from `useAuth()`.

The confirm dialog states plainly what is and isn't deleted:

> Delete the upload record for "<filename>"?
> Imported print jobs, costs and analytics are NOT affected. This cannot be undone.

On success, invalidate `['uploads', id]`. Analytics keys are deliberately not
invalidated — nothing analytics reads has changed.

Rows also gain an amber `N skipped` badge when `rows_skipped > 0`, so a problem
import is visible without opening the drawer.

**Client-side gating is cosmetic.** Hiding the button is a UX affordance, not
security; the `OwnerUser` dependency in §3 is what actually enforces it.

## 6. Deliberately unchanged

`DELETE /api/v1/printers/{printer_id}/uploads/clear` (`print_jobs.py:297`) keeps its
current behaviour and its `CurrentUser` (not `OwnerUser`) dependency.

Known and accepted risk: that endpoint deletes all print jobs *and* batches for a
printer, and any authenticated user with access to the printer — including a
`print_person` — can trigger it from the printer page (`PrinterDetailPage.tsx:481`).
Restricting it was considered and explicitly declined for this iteration. Revisit
if a non-owner ever wipes a printer by accident.

## 7. Related: the n8n triple-import

This spec does not fix the cause of the duplicate rows, only makes them removable.

Root cause, confirmed from n8n execution `91560`: `Resolve folder IDs` is a Set
node, which runs once per input item. It receives 3 items (the `Inbox`, `Archive`
and `Error` folders) and emits 3 identical copies, so `List CSVs in Inbox` runs
three times against the same folder and the same file is POSTed three times within
a single execution. The count equals the number of subfolders, not a retry count.

Backend dedup on `(printer_id, job_id, recorded_at)` works correctly — runs 2 and 3
return `rows_imported: 0`. No duplicate print jobs are created; only surplus
`upload_batches` rows. Fix is a one-node change in n8n (emit a single item), tracked
outside this spec.

## 8. Testing

Backend (`backend/tests/`):

1. **Batch detail returns skipped_details** — import a CSV with one bad row, GET the
   batch, assert the reason is present.
2. **Cross-printer batch detail 404s** — batch belonging to printer A is not readable
   via printer B's path.
3. **Delete preserves print jobs** — the critical one. Import jobs, delete the batch,
   then assert `print_jobs` count is unchanged and every `upload_batch_id` is `NULL`.
   This is the regression guard for the cascade trap in §3.
4. **Delete is owner-only** — a `print_person` token gets 403 and the batch survives.
5. **List includes `source`** — so the UI can badge automated imports.

All five live in `backend/tests/integration/test_upload_history.py`. New shared
fixtures in `conftest.py`: `second_printer`, `print_person_user`, `owner_token`,
`print_person_token`.

Frontend: covered by `tsc --noEmit`; no component test framework is set up in this
project yet.

## 9. Outcome

Built 2026-07-24 following the test order above. All 5 new tests pass; full backend
suite 51 passed. Frontend typecheck clean.

Note on test 2 (cross-printer 404): it passed before implementation too, because an
absent route also 404s. It only became a meaningful assertion once the route existed
— worth remembering if it is ever refactored.
