# Automated CSV Ingest from Google Drive (via n8n)

**Date:** 2026-05-24
**Status:** Approved for planning
**Owner:** nankshr

## Problem

Production drops daily print-job CSVs that today must be uploaded manually through the PrintSight UI (`POST /printers/{id}/uploads` in `backend/app/routers/print_jobs.py`). A prior attempt to ingest via FTP did not work. As an interim trial, files will be dropped into Google Drive at end of business day, and we want them to flow into PrintSight automatically: import → archive on success, quarantine on failure with an error log. The Drive channel may later be replaced by FTP/SFTP/S3, so the app must not be coupled to Drive.

## Goals

- Automate ingestion of CSV files dropped into a Drive folder per printer.
- Reuse the existing import pipeline — no parallel logic, no divergence.
- Keep the channel (Drive today, something else later) outside the app.
- On success, move the source file to an `Archive` folder; on failure, move it to an `Error` folder with a sibling `.error.log`.
- No corrupt/duplicate data: validate before insert; rely on the existing dedup mechanism.

## Non-Goals

- Configurable Drive paths inside the app's `.env` (paths live in n8n).
- Per-printer ingest tokens, audit-per-source, retry/backoff inside the app (n8n handles retry).
- A UI surface for monitoring n8n runs.

## Architecture

```
[Production] → CSV → Google Drive: /<root>/<printer_id>/Inbox/file.csv
                              │
                              ▼
                       [n8n workflow]
                       1. Drive trigger (new file in Inbox)
                       2. Wait 60s
                       3. Download file bytes
                       4. POST multipart to PrintSight import API
                          with header: X-API-Key: $INGEST_API_KEY
                       5. Branch on HTTP status:
                          ├── 2xx → move source file to /<printer_id>/Archive/
                          └── non-2xx → move source file to /<printer_id>/Error/
                                       + write <filename>.error.log alongside it
                              │
                              ▼
                       [PrintSight FastAPI]
                       POST /printers/{printer_id}/uploads/import
                         - API-key auth (no user session)
                         - calls shared csv_import_service.import_csv_for_printer(...)
                         - returns structured JSON (see contract below)
```

Two systems, single direction of data flow. The app does not know Drive exists. n8n does not know how imports work. Swapping channels in the future means replacing only the n8n trigger node.

## Components & Files

### New
- `backend/app/services/csv_import_service.py` — shared import function `import_csv_for_printer(db, printer_id, file_bytes, filename, source, uploaded_by_user_id) -> ImportResult`. Returns a dataclass with `batch_id`, `rows_total`, `rows_imported`, `rows_skipped`, `skipped_rows[]` (row_number + reason).
- `backend/app/auth/api_key.py` — FastAPI dependency `require_ingest_api_key` that validates `X-API-Key` header against `settings.ingest_api_key`. Returns `401` on mismatch, `503` if no key is configured server-side (refuse rather than silently allow).
- New route in `backend/app/routers/print_jobs.py`: `POST /printers/{printer_id}/uploads/import` — multipart `file` field, optional `source_filename` form field; auth via `require_ingest_api_key`; calls the shared service and returns the contract below.
- `INGEST_API_KEY` added to `backend/app/config.py` `Settings` (optional `str | None`, default `None`).
- Tests in `backend/tests/` covering: missing key → 401; wrong key → 401; key not configured → 503; happy path with a small CSV; duplicate file re-post → 200 with `rows_imported: 0`; malformed CSV → 400 with structured error; non-existent printer → 404; existing manual upload endpoint still works unchanged.

### Modified
- `backend/app/routers/print_jobs.py` — the body of `upload_csv` (manual SSE handler) is refactored to call `csv_import_service.import_csv_for_printer`. SSE progress events are preserved by having the service expose either a generator or progress-callback hook. **Acceptance:** existing manual upload behavior — including the SSE event stream and `UploadSource.manual` — is unchanged from the user's perspective.
- `backend/app/models/upload.py` — add `UploadSource.automated` enum value (plus matching Alembic migration) so batches created via the new endpoint are distinguishable from manual uploads in queries/reports.

## Endpoint Contract

**Route:** `POST /printers/{printer_id}/uploads/import`
**Auth:** header `X-API-Key: <token>` matching `INGEST_API_KEY`. Missing/wrong → `401`. Not configured on server → `503`.
**Request:** `multipart/form-data`
- `file` (required) — the CSV bytes.
- `source_filename` (optional) — original filename as seen by n8n; falls back to `file.filename`.

**Response — success (200):**
```json
{
  "status": "success",
  "batch_id": 123,
  "printer_id": 42,
  "rows_total": 1492,
  "rows_imported": 1480,
  "rows_skipped": 12,
  "source_filename": "2026-05-23_jobs.csv"
}
```

**Response — failure:**
```json
{
  "status": "error",
  "error_code": "INVALID_CSV | PRINTER_NOT_FOUND | COLUMN_MAPPING_MISSING | UNAUTHORIZED | INTERNAL",
  "message": "Human-readable summary",
  "details": ["row 5: missing job_id", "row 9: invalid date"],
  "source_filename": "2026-05-23_jobs.csv"
}
```

HTTP status codes:
- `200` — import succeeded (even if some rows skipped).
- `400` — `INVALID_CSV`, `COLUMN_MAPPING_MISSING`.
- `401` — `UNAUTHORIZED`.
- `404` — `PRINTER_NOT_FOUND`.
- `500` — `INTERNAL`.

The `message` + `details` fields are written verbatim by n8n into `<filename>.error.log`.

## Data Integrity & Idempotency

The existing import already dedupes on `(printer_id, job_id, recorded_at)` — see `backend/app/routers/print_jobs.py:348-352`, which loads existing keys into a set and skips matching rows. This protection is inherited by the new endpoint because both call the same service.

Consequences:
- Re-POSTing the identical CSV returns `200` with `rows_imported: 0`, `rows_skipped: <all rows>`. The Drive file moves to Archive. Safe.
- A CSV with a mix of new + previously-seen jobs inserts only the new rows. Skipped rows are reported per-row in the response.
- A CSV that fails to parse or is missing required columns returns a 4xx **before any DB writes**. No partial state.

No additional per-file dedup (e.g., by filename or SHA) is added.

## `.env` Configuration

Only one new variable in the app:

```
INGEST_API_KEY=<long random string, generated once>
```

All Drive-side configuration (root folder ID, `Inbox`/`Archive`/`Error` subfolder names, 60s wait, retry policy, credentials) lives in n8n as workflow variables — that is the explicit boundary that lets us swap channels later.

## n8n Workflow (reference, not part of this repo)

1. **Google Drive Trigger** — `File Created` on `/<root>/<printer_id>/Inbox/` (per printer, or one trigger watching the root recursively).
2. **Wait** — 60 seconds (lets production finish writing the file).
3. **Google Drive — Download File** — fetch the file bytes.
4. **HTTP Request** — `POST {PRINTSIGHT_URL}/printers/{{ $json.printerId }}/uploads/import`, multipart body with `file`, header `X-API-Key: {{ $credentials.printsightIngest }}`.
5. **IF** — branch on `$response.statusCode < 400`.
   - **True branch:** Drive → Move File to `/<printer_id>/Archive/`.
   - **False branch:** Drive → Move File to `/<printer_id>/Error/`, then Drive → Create File `<filename>.error.log` in the same folder, content = `{{ $response.body.message }}\n\n{{ $response.body.details.join("\n") }}`.

Printer ID is extracted from the source folder path. The n8n flow is built and tested after the endpoint is verified manually with curl.

## Build Order

1. Implement and unit-test the endpoint + shared service.
2. Verify manually with `curl` against a real CSV (happy path, duplicate re-post, malformed file).
3. Configure n8n workflow against the live endpoint.

## Open Questions

None — all decisions captured above.
