# Drive CSV Ingest — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a headless, API-key-authenticated CSV import endpoint at `POST /printers/{printer_id}/uploads/import` so an external orchestrator (n8n) can drop CSVs from Google Drive into PrintSight, reusing the existing import + dedup pipeline.

**Architecture:** Extract today's CSV import logic from the SSE handler in `backend/app/routers/print_jobs.py` into a reusable service function `import_csv_for_printer(...)`. The existing manual upload (SSE) endpoint and the new headless endpoint both call it. The new endpoint authenticates via an `X-API-Key` header validated against `INGEST_API_KEY` in `.env`. Returns a structured JSON contract so n8n can route the source file to Archive (on `2xx`) or Error (on `4xx/5xx`, writing `<filename>.error.log` from `message` + `details`).

**Tech Stack:** FastAPI, SQLAlchemy, Alembic, Pydantic v2 (`BaseSettings`), pandas, pytest, pytest's `TestClient` from `fastapi.testclient`.

**Spec:** `docs/superpowers/specs/2026-05-24-drive-csv-ingest-design.md`

---

## File Structure

### Create
- `backend/app/services/csv_import_service.py` — sync `import_csv_for_printer(...)` core + `ImportResult` dataclass + `ImportError` exception with structured `error_code`/`details`. All row-parsing helpers move here from `routers/print_jobs.py`.
- `backend/app/auth/api_key.py` — FastAPI dependency `require_ingest_api_key` (validates `X-API-Key` against `settings.ingest_api_key`).
- `backend/alembic/versions/006_r15_upload_source_automated.py` — extend the `upload_source` Postgres enum with the `automated` value.
- `backend/tests/conftest.py` — shared pytest fixtures (TestClient, test DB session, sample printer with column mapping, env-var override for `INGEST_API_KEY`).
- `backend/tests/integration/test_drive_ingest.py` — endpoint tests (auth, happy path, dedup re-post, malformed CSV, missing printer, unconfigured key).
- `backend/tests/unit/test_csv_import_service.py` — service-level tests (pure parsing, dedup, structured errors).

### Modify
- `backend/app/config.py` — add `ingest_api_key: str | None = None` field.
- `backend/app/models/upload.py` — add `UploadSource.automated = "automated"`.
- `backend/app/routers/print_jobs.py` — replace the body of `upload_csv` (the SSE manual upload) so it calls `csv_import_service.import_csv_for_printer(...)` with a progress callback that yields SSE events. Add the new headless `POST /import` route. Remove now-duplicated row helpers (they live in the service).

---

## Task 1 — Add config & enum value (with migration)

**Files:**
- Modify: `backend/app/config.py`
- Modify: `backend/app/models/upload.py:28-31`
- Create: `backend/alembic/versions/006_r15_upload_source_automated.py`
- Test: `backend/tests/unit/test_config_ingest_key.py` (new, deleted after Task 1's commit — it's a transient sanity check)

- [ ] **Step 1: Write failing test for the new setting**

Create `backend/tests/unit/test_config_ingest_key.py`:

```python
"""Sanity check that INGEST_API_KEY flows from env into settings."""

from __future__ import annotations

import importlib

import pytest


def test_ingest_api_key_defaults_to_none(monkeypatch):
    monkeypatch.delenv("INGEST_API_KEY", raising=False)
    from app import config as cfg
    cfg.get_settings.cache_clear()
    s = cfg.Settings()
    assert s.ingest_api_key is None


def test_ingest_api_key_reads_env(monkeypatch):
    monkeypatch.setenv("INGEST_API_KEY", "test-key-123")
    from app import config as cfg
    cfg.get_settings.cache_clear()
    s = cfg.Settings()
    assert s.ingest_api_key == "test-key-123"
```

- [ ] **Step 2: Run the test and confirm it fails**

Run: `cd backend && pytest tests/unit/test_config_ingest_key.py -v`
Expected: FAIL with `AttributeError: 'Settings' object has no attribute 'ingest_api_key'`.

- [ ] **Step 3: Add the setting**

Edit `backend/app/config.py`, add inside the `Settings` class (after the `max_csv_upload_size_mb` line):

```python
    # Ingest (headless API for n8n / external pushers)
    ingest_api_key: str | None = None
```

- [ ] **Step 4: Confirm config test passes**

Run: `cd backend && pytest tests/unit/test_config_ingest_key.py -v`
Expected: PASS (2/2).

- [ ] **Step 5: Add the enum value**

Edit `backend/app/models/upload.py`, lines 28-31:

```python
class UploadSource(str, enum.Enum):
    manual = "manual"
    api_push = "api_push"
    automated = "automated"
```

- [ ] **Step 6: Create the Alembic migration**

Create `backend/alembic/versions/006_r15_upload_source_automated.py`:

```python
"""Rev 1.5 — extend upload_source enum with 'automated'.

Revision ID: 006
Revises: 005
Create Date: 2026-05-24
"""

from __future__ import annotations

from alembic import op

revision = "006"
down_revision = "005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Postgres enums can be extended but not shrunk transactionally.
    op.execute("ALTER TYPE upload_source ADD VALUE IF NOT EXISTS 'automated'")


def downgrade() -> None:
    # No-op: Postgres doesn't support removing enum values without recreating the type.
    # Downgrade leaves the value in place; existing rows referencing it would break a true removal.
    pass
```

- [ ] **Step 7: Apply the migration locally**

Run: `cd backend && alembic upgrade head`
Expected: applies revision 006 cleanly. Verify with `alembic current` showing `006 (head)`.

- [ ] **Step 8: Delete the transient config test**

The config sanity check has served its purpose and the rest of the suite covers the integration. Delete the file:

Run: `rm backend/tests/unit/test_config_ingest_key.py`

- [ ] **Step 9: Commit**

```bash
git add backend/app/config.py backend/app/models/upload.py backend/alembic/versions/006_r15_upload_source_automated.py
git commit -m "feat(ingest): add INGEST_API_KEY config and UploadSource.automated"
```

---

## Task 2 — Extract `csv_import_service`

This is the largest task. It moves all CSV row parsing and the import loop out of `routers/print_jobs.py` into a service, then makes the existing SSE manual-upload handler call the service via a progress callback. **No behaviour change** is expected for the manual upload path.

**Files:**
- Create: `backend/app/services/csv_import_service.py`
- Modify: `backend/app/routers/print_jobs.py:1-50, 180-300, 305-427`
- Test: `backend/tests/unit/test_csv_import_service.py`

- [ ] **Step 1: Write the failing service tests**

Create `backend/tests/unit/test_csv_import_service.py`:

```python
"""Unit tests for csv_import_service core."""

from __future__ import annotations

import io
from datetime import datetime, timezone
from decimal import Decimal

import pytest

# These imports will fail until the module exists — that is the point.
from app.services.csv_import_service import (
    ImportError as CsvImportError,
    ImportResult,
    import_csv_for_printer,
)


SAMPLE_CSV = (
    "job_id,recorded_at,printed_pages,color_pages,bw_pages\n"
    "JOB-1,2026-05-23 10:00:00,10,4,6\n"
    "JOB-2,2026-05-23 10:05:00,2,0,2\n"
)


def test_returns_import_result_dataclass(db_session, printer_with_mapping):
    result = import_csv_for_printer(
        db=db_session,
        printer_id=printer_with_mapping.id,
        raw_bytes=SAMPLE_CSV.encode("utf-8"),
        filename="test.csv",
        source="automated",
        uploaded_by_user_id=None,
    )
    assert isinstance(result, ImportResult)
    assert result.rows_total == 2
    assert result.rows_imported == 2
    assert result.rows_skipped == 0
    assert result.batch_id > 0


def test_duplicate_repost_imports_zero(db_session, printer_with_mapping):
    args = dict(
        db=db_session,
        printer_id=printer_with_mapping.id,
        raw_bytes=SAMPLE_CSV.encode("utf-8"),
        filename="test.csv",
        source="automated",
        uploaded_by_user_id=None,
    )
    first = import_csv_for_printer(**args)
    second = import_csv_for_printer(**args)
    assert first.rows_imported == 2
    assert second.rows_imported == 0
    assert second.rows_skipped == 2


def test_unparseable_csv_raises_import_error(db_session, printer_with_mapping):
    with pytest.raises(CsvImportError) as exc_info:
        import_csv_for_printer(
            db=db_session,
            printer_id=printer_with_mapping.id,
            raw_bytes=b"\x00\x01not a csv",
            filename="bad.bin",
            source="automated",
            uploaded_by_user_id=None,
        )
    assert exc_info.value.error_code == "INVALID_CSV"
    assert exc_info.value.message


def test_unknown_printer_raises(db_session):
    with pytest.raises(CsvImportError) as exc_info:
        import_csv_for_printer(
            db=db_session,
            printer_id=999999,
            raw_bytes=SAMPLE_CSV.encode("utf-8"),
            filename="t.csv",
            source="automated",
            uploaded_by_user_id=None,
        )
    assert exc_info.value.error_code == "PRINTER_NOT_FOUND"


def test_progress_callback_invoked(db_session, printer_with_mapping):
    seen: list[tuple[int, int]] = []
    import_csv_for_printer(
        db=db_session,
        printer_id=printer_with_mapping.id,
        raw_bytes=SAMPLE_CSV.encode("utf-8"),
        filename="t.csv",
        source="automated",
        uploaded_by_user_id=None,
        progress_callback=lambda done, total: seen.append((done, total)),
    )
    assert seen, "progress_callback was never called"
    assert seen[-1][0] == seen[-1][1]
```

You will also need the shared fixtures `db_session` and `printer_with_mapping`. They are created in Task 3's conftest step — write them now in `backend/tests/conftest.py`:

```python
"""Shared pytest fixtures."""

from __future__ import annotations

import os
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.config import get_settings, settings
from app.database import Base, get_db
from app.main import app
from app.models.printer import Printer
from app.models.user import User, UserRole


# Use a separate test DB if TEST_DATABASE_URL is set, otherwise reuse dev DB.
TEST_DB_URL = os.environ.get("TEST_DATABASE_URL", settings.database_url)


@pytest.fixture(scope="session")
def engine():
    eng = create_engine(TEST_DB_URL)
    Base.metadata.create_all(bind=eng)
    yield eng
    eng.dispose()


@pytest.fixture
def db_session(engine):
    Session = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    s = Session()
    try:
        yield s
    finally:
        s.rollback()
        s.close()


@pytest.fixture
def test_user(db_session) -> User:
    u = User(
        email=f"ingest-test-{os.getpid()}@example.com",
        hashed_password="x",
        full_name="Ingest Test",
        role=UserRole.admin,
        is_active=True,
    )
    db_session.add(u)
    db_session.commit()
    db_session.refresh(u)
    yield u
    db_session.delete(u)
    db_session.commit()


@pytest.fixture
def printer_with_mapping(db_session, test_user) -> Printer:
    p = Printer(
        owner_id=test_user.id,
        name="Test Printer",
        column_mapping={
            "job_id": "job_id",
            "recorded_at": "recorded_at",
            "printed_pages": "printed_pages",
            "color_pages": "color_pages",
            "bw_pages": "bw_pages",
        },
    )
    db_session.add(p)
    db_session.commit()
    db_session.refresh(p)
    yield p
    db_session.delete(p)
    db_session.commit()


@pytest.fixture(autouse=True)
def _ingest_key_env(monkeypatch):
    """Set a known ingest key for all tests; clear cached settings."""
    monkeypatch.setenv("INGEST_API_KEY", "test-ingest-key")
    get_settings.cache_clear()


@pytest.fixture
def client():
    return TestClient(app)
```

> If your `Printer` model requires additional non-null fields beyond what is shown above, add them — match the columns already present in `backend/app/models/printer.py`. Do not invent fields.

- [ ] **Step 2: Run service tests and confirm they fail at the import line**

Run: `cd backend && pytest tests/unit/test_csv_import_service.py -v`
Expected: collection error — `ModuleNotFoundError: No module named 'app.services.csv_import_service'`.

- [ ] **Step 3: Create the service module**

Create `backend/app/services/csv_import_service.py`. This is a near-direct lift of the existing handler — keep it byte-for-byte equivalent for parsing, dedup, and batch sizing. The only differences are: (a) no SSE generator, (b) errors raised as `ImportError`, (c) optional `progress_callback`.

```python
"""Shared CSV import core used by manual SSE upload and headless API.

Extracted from routers/print_jobs.py to allow two entry points to share the
same parsing, dedup, and batched-insert logic. No behaviour change versus
the original handler; only the surface (sync function vs generator) differs.
"""

from __future__ import annotations

import io
import logging
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Any, Callable, Optional

import pandas as pd
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models.printer import Printer
from app.models.upload import (
    PrintJob,
    UploadBatch,
    UploadSource,
    UploadStatus,
)

logger = logging.getLogger(__name__)

_UPLOAD_BATCH = 500


@dataclass
class ImportResult:
    batch_id: int
    printer_id: int
    rows_total: int
    rows_imported: int
    rows_skipped: int
    skipped_details: list[dict] = field(default_factory=list)


class ImportError(Exception):
    """Structured error raised by import_csv_for_printer.

    error_code values match the spec contract:
      INVALID_CSV, PRINTER_NOT_FOUND, COLUMN_MAPPING_MISSING, INTERNAL.
    """

    def __init__(self, error_code: str, message: str, details: list[str] | None = None):
        super().__init__(message)
        self.error_code = error_code
        self.message = message
        self.details = details or []


# --- Row parsing helpers (lifted verbatim from routers/print_jobs.py) -------

def _col(row, mapping, target_key, default=None):
    # MOVE the existing _col implementation from routers/print_jobs.py here.
    ...


def _parse_dt(val):
    # MOVE the existing _parse_dt implementation from routers/print_jobs.py here.
    ...


def _parse_int(val, default=0):
    # MOVE existing impl here.
    ...


def _parse_decimal(val):
    # MOVE existing impl here.
    ...


def _parse_bool(val):
    # MOVE existing impl here.
    ...


def _parse_coverage(val):
    # MOVE existing impl here.
    ...


def _str_or_none(val: Any) -> str | None:
    s = str(val).strip() if val is not None else ""
    return s if s and s.lower() not in ("nan", "none") else None


def _build_job(row, mapping, printer_id, batch_id) -> PrintJob:
    # MOVE the existing _build_job implementation here verbatim.
    ...


# --- Public entry point ------------------------------------------------------

def import_csv_for_printer(
    *,
    db: Session,
    printer_id: int,
    raw_bytes: bytes,
    filename: str,
    source: str,
    uploaded_by_user_id: Optional[int],
    progress_callback: Optional[Callable[[int, int], None]] = None,
) -> ImportResult:
    """Run the full CSV → DB import pipeline for one printer.

    Raises ImportError on validation/precondition failures *before* any DB write.
    On success, persists an UploadBatch + PrintJob rows and returns ImportResult.
    """
    # 1. Resolve printer / mapping
    printer = db.query(Printer).filter(Printer.id == printer_id).first()
    if not printer:
        raise ImportError("PRINTER_NOT_FOUND", f"Printer {printer_id} not found")
    if not printer.column_mapping:
        raise ImportError(
            "COLUMN_MAPPING_MISSING",
            f"Printer {printer_id} has no column_mapping configured",
        )

    # 2. Parse CSV (no DB writes yet)
    try:
        df = pd.read_csv(io.BytesIO(raw_bytes), dtype=str, keep_default_na=False)
    except Exception as exc:
        raise ImportError("INVALID_CSV", f"Could not parse CSV: {exc}") from exc

    df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]
    mapping = {k.lower(): v.strip().lower().replace(" ", "_") for k, v in (printer.column_mapping or {}).items()}
    total_rows = len(df)

    # 3. Resolve UploadSource enum
    try:
        source_enum = UploadSource(source)
    except ValueError as exc:
        raise ImportError("INTERNAL", f"Unknown upload source: {source}") from exc

    # 4. Create the batch + load existing dedup keys, in a single short session.
    session = SessionLocal()
    try:
        batch = UploadBatch(
            printer_id=printer_id,
            uploaded_by_user_id=uploaded_by_user_id,
            source=source_enum,
            filename=filename,
            rows_total=total_rows,
            status=UploadStatus.processing,
        )
        session.add(batch)
        session.flush()
        batch_id = batch.id
        existing_keys: set = set(
            (r[0], r[1]) for r in
            session.query(PrintJob.job_id, PrintJob.recorded_at)
            .filter(PrintJob.printer_id == printer_id).all()
        )
        session.commit()
    finally:
        session.close()

    if progress_callback:
        progress_callback(0, total_rows)

    imported = 0
    skipped: list[dict] = []
    batch_keys: set = set()

    df_records = [(idx, row) for idx, row in df.iterrows()]
    for chunk_start in range(0, total_rows, _UPLOAD_BATCH):
        chunk = df_records[chunk_start:chunk_start + _UPLOAD_BATCH]
        jobs_to_add: list[PrintJob] = []
        chunk_skipped: list[dict] = []

        for idx, row in chunk:
            row_num = int(str(idx)) + 2
            job_id_raw = _col(row, mapping, "job_id") or _col(row, mapping, "jobid") or _col(row, mapping, "id")
            if not job_id_raw or str(job_id_raw).strip() in ("", "nan"):
                chunk_skipped.append({"row_number": row_num, "reason": "Missing job_id"})
                continue
            job_id = str(job_id_raw).strip()
            recorded_at = _parse_dt(
                _col(row, mapping, "recorded_at")
                or _col(row, mapping, "printed_at")
                or _col(row, mapping, "date")
            )
            dup_key = (job_id, recorded_at)
            if dup_key in existing_keys or dup_key in batch_keys:
                chunk_skipped.append({"row_number": row_num, "reason": f"Duplicate job_id={job_id}"})
                continue
            jobs_to_add.append(_build_job(row, mapping, printer_id, batch_id))
            batch_keys.add(dup_key)

        if jobs_to_add:
            chunk_session = SessionLocal()
            try:
                chunk_session.add_all(jobs_to_add)
                chunk_session.commit()
                imported += len(jobs_to_add)
            except Exception as e:
                chunk_session.rollback()
                chunk_skipped.append({"row_number": 0, "reason": f"DB error: {str(e)[:80]}"})
            finally:
                chunk_session.close()

        skipped.extend(chunk_skipped)
        done_rows = min(chunk_start + _UPLOAD_BATCH, total_rows)
        if progress_callback:
            progress_callback(done_rows, total_rows)

    # Finalise batch row
    final_session = SessionLocal()
    try:
        b = final_session.query(UploadBatch).filter(UploadBatch.id == batch_id).first()
        if b:
            b.rows_imported = imported
            b.rows_skipped = len(skipped)
            b.skipped_details = skipped
            b.status = UploadStatus.completed
            final_session.commit()
    finally:
        final_session.close()

    return ImportResult(
        batch_id=batch_id,
        printer_id=printer_id,
        rows_total=total_rows,
        rows_imported=imported,
        rows_skipped=len(skipped),
        skipped_details=skipped,
    )
```

> The `...` placeholders for helpers (`_col`, `_parse_dt`, `_parse_int`, `_parse_decimal`, `_parse_bool`, `_parse_coverage`, `_build_job`) MUST be replaced with the exact existing implementations from `backend/app/routers/print_jobs.py`. Use `grep -n "^def _col\|^def _parse\|^def _build_job\|^def _str_or_none" backend/app/routers/print_jobs.py` to locate them and copy verbatim. Do not rewrite them.

- [ ] **Step 4: Run service tests and confirm they pass**

Run: `cd backend && pytest tests/unit/test_csv_import_service.py -v`
Expected: 5/5 PASS.

- [ ] **Step 5: Refactor the manual SSE handler to call the service**

Edit `backend/app/routers/print_jobs.py`. Replace the body of `upload_csv` (currently at lines ~305-427) with a thin shim that calls the service and yields SSE progress via a queue:

```python
@router.post("")
async def upload_csv(
    printer_id: int,
    current_user: CurrentUser,
    db: Session = Depends(get_db),
    file: UploadFile = File(...),
):
    """Upload CSV and stream SSE import progress events (manual UI upload)."""
    from app.services.csv_import_service import (
        ImportError as CsvImportError,
        import_csv_for_printer,
    )
    import queue as _queue
    import threading as _threading

    p = _get_printer_or_403(db, printer_id, current_user.id)

    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only .csv files are accepted")

    raw = await file.read()
    if len(raw) > MAX_BYTES:
        raise HTTPException(
            status_code=400,
            detail=f"File exceeds {settings.max_csv_upload_size_mb} MB limit",
        )

    user_id = current_user.id
    filename = file.filename
    q: _queue.Queue = _queue.Queue()
    _SENTINEL = object()

    def _run():
        try:
            result = import_csv_for_printer(
                db=db,
                printer_id=printer_id,
                raw_bytes=raw,
                filename=filename,
                source=UploadSource.manual.value,
                uploaded_by_user_id=user_id,
                progress_callback=lambda done, total: q.put(("progress", done, total)),
            )
            q.put(("done", result))
        except CsvImportError as e:
            q.put(("error", e))
        except Exception as e:  # noqa: BLE001 — surface unexpected errors to client
            q.put(("error", CsvImportError("INTERNAL", str(e))))
        finally:
            q.put(_SENTINEL)

    _threading.Thread(target=_run, daemon=True).start()

    def generate():
        while True:
            item = q.get()
            if item is _SENTINEL:
                return
            kind = item[0]
            if kind == "progress":
                _, done, total = item
                yield f"data: {_json_upload.dumps({'done': done, 'total': total})}\n\n"
            elif kind == "done":
                r = item[1]
                yield f"data: {_json_upload.dumps({'done': r.rows_total, 'total': r.rows_total, 'complete': True, 'batch_id': r.batch_id, 'rows_total': r.rows_total, 'rows_imported': r.rows_imported, 'rows_skipped': r.rows_skipped, 'skipped_details': r.skipped_details[:20], 'message': f'Imported {r.rows_imported} jobs, skipped {r.rows_skipped}'})}\n\n"
            elif kind == "error":
                e = item[1]
                yield f"data: {_json_upload.dumps({'complete': True, 'error': e.error_code, 'message': e.message, 'details': e.details})}\n\n"

    return _StreamingResponseUpload(generate(), media_type="text/event-stream")
```

Then **delete** the now-duplicated helpers from `routers/print_jobs.py`: `_col`, `_parse_dt`, `_parse_int`, `_parse_decimal`, `_parse_bool`, `_parse_coverage`, `_str_or_none`, `_build_job`, and the `_UPLOAD_BATCH` constant. Update remaining references in the same file (e.g. `recompute_costs` if it uses `_parse_dt` — if so, import from the service module: `from app.services.csv_import_service import _parse_dt`).

> Run `grep -n "_col\|_parse_dt\|_parse_int\|_parse_decimal\|_parse_bool\|_parse_coverage\|_str_or_none\|_build_job\|_UPLOAD_BATCH" backend/app/routers/print_jobs.py` after deletion to confirm no orphan references remain in this file.

- [ ] **Step 6: Manually smoke-test the manual upload still works**

Start the backend (`docker compose -f docker-compose.dev.yml up -d` or however the project boots locally), open the UI, upload a small CSV through the existing manual upload, watch the SSE progress bar to completion. Confirm the upload appears in the batches list. **This is the regression check** — the existing path must look identical to before.

- [ ] **Step 7: Commit**

```bash
git add backend/app/services/csv_import_service.py backend/app/routers/print_jobs.py backend/tests/unit/test_csv_import_service.py backend/tests/conftest.py
git commit -m "refactor(ingest): extract csv_import_service from print_jobs router"
```

---

## Task 3 — API-key auth dependency

**Files:**
- Create: `backend/app/auth/api_key.py`
- Test: `backend/tests/unit/test_api_key_dep.py`

- [ ] **Step 1: Write failing tests**

Create `backend/tests/unit/test_api_key_dep.py`:

```python
"""Tests for the X-API-Key ingest auth dependency."""

from __future__ import annotations

import pytest
from fastapi import FastAPI, Depends, HTTPException
from fastapi.testclient import TestClient

from app.auth.api_key import require_ingest_api_key
from app.config import get_settings


@pytest.fixture
def mini_app():
    app = FastAPI()

    @app.get("/protected")
    def protected(_: None = Depends(require_ingest_api_key)):
        return {"ok": True}

    return app


def test_rejects_missing_header(mini_app, monkeypatch):
    monkeypatch.setenv("INGEST_API_KEY", "configured")
    get_settings.cache_clear()
    c = TestClient(mini_app)
    r = c.get("/protected")
    assert r.status_code == 401
    assert r.json()["detail"]["error_code"] == "UNAUTHORIZED"


def test_rejects_wrong_header(mini_app, monkeypatch):
    monkeypatch.setenv("INGEST_API_KEY", "configured")
    get_settings.cache_clear()
    c = TestClient(mini_app)
    r = c.get("/protected", headers={"X-API-Key": "wrong"})
    assert r.status_code == 401


def test_accepts_correct_header(mini_app, monkeypatch):
    monkeypatch.setenv("INGEST_API_KEY", "configured")
    get_settings.cache_clear()
    c = TestClient(mini_app)
    r = c.get("/protected", headers={"X-API-Key": "configured"})
    assert r.status_code == 200


def test_503_when_server_not_configured(mini_app, monkeypatch):
    monkeypatch.delenv("INGEST_API_KEY", raising=False)
    get_settings.cache_clear()
    c = TestClient(mini_app)
    r = c.get("/protected", headers={"X-API-Key": "anything"})
    assert r.status_code == 503
    assert r.json()["detail"]["error_code"] == "INTERNAL"
```

- [ ] **Step 2: Run and confirm failure**

Run: `cd backend && pytest tests/unit/test_api_key_dep.py -v`
Expected: `ModuleNotFoundError: app.auth.api_key`.

- [ ] **Step 3: Create the dependency**

Create `backend/app/auth/api_key.py`:

```python
"""X-API-Key dependency for headless ingest endpoints."""

from __future__ import annotations

from fastapi import Header, HTTPException, status

from app.config import settings


def require_ingest_api_key(x_api_key: str | None = Header(default=None)) -> None:
    """Validate the inbound X-API-Key header against settings.ingest_api_key.

    - 503 if no key is configured server-side (refuse to silently allow).
    - 401 if the header is missing or does not match.
    """
    configured = settings.ingest_api_key
    if not configured:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "status": "error",
                "error_code": "INTERNAL",
                "message": "Ingest API key is not configured on the server",
                "details": [],
            },
        )
    if not x_api_key or x_api_key != configured:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "status": "error",
                "error_code": "UNAUTHORIZED",
                "message": "Invalid or missing X-API-Key header",
                "details": [],
            },
        )
```

- [ ] **Step 4: Run and confirm 4/4 pass**

Run: `cd backend && pytest tests/unit/test_api_key_dep.py -v`
Expected: 4/4 PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/auth/api_key.py backend/tests/unit/test_api_key_dep.py
git commit -m "feat(ingest): add X-API-Key auth dependency for headless endpoints"
```

---

## Task 4 — Headless import endpoint

**Files:**
- Modify: `backend/app/routers/print_jobs.py` (add the new route)
- Test: `backend/tests/integration/test_drive_ingest.py`

- [ ] **Step 1: Write the failing integration tests**

Create `backend/tests/integration/test_drive_ingest.py`:

```python
"""Integration tests for POST /printers/{id}/uploads/import."""

from __future__ import annotations

import io


SAMPLE_CSV = (
    "job_id,recorded_at,printed_pages,color_pages,bw_pages\n"
    "JOB-1,2026-05-23 10:00:00,10,4,6\n"
    "JOB-2,2026-05-23 10:05:00,2,0,2\n"
).encode("utf-8")


def _post(client, printer_id, body=SAMPLE_CSV, key="test-ingest-key", filename="t.csv"):
    files = {"file": (filename, io.BytesIO(body), "text/csv")}
    headers = {"X-API-Key": key} if key else {}
    return client.post(f"/printers/{printer_id}/uploads/import", files=files, headers=headers)


def test_happy_path_returns_200_with_contract(client, printer_with_mapping):
    r = _post(client, printer_with_mapping.id)
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["status"] == "success"
    assert j["printer_id"] == printer_with_mapping.id
    assert j["rows_total"] == 2
    assert j["rows_imported"] == 2
    assert j["rows_skipped"] == 0
    assert isinstance(j["batch_id"], int)
    assert j["source_filename"] == "t.csv"


def test_duplicate_repost_skips_all(client, printer_with_mapping):
    r1 = _post(client, printer_with_mapping.id)
    r2 = _post(client, printer_with_mapping.id)
    assert r1.status_code == 200
    assert r2.status_code == 200
    j2 = r2.json()
    assert j2["rows_imported"] == 0
    assert j2["rows_skipped"] == 2


def test_missing_api_key_returns_401(client, printer_with_mapping):
    r = _post(client, printer_with_mapping.id, key=None)
    assert r.status_code == 401
    assert r.json()["detail"]["error_code"] == "UNAUTHORIZED"


def test_wrong_api_key_returns_401(client, printer_with_mapping):
    r = _post(client, printer_with_mapping.id, key="nope")
    assert r.status_code == 401


def test_unknown_printer_returns_404(client):
    r = _post(client, 999999)
    assert r.status_code == 404
    assert r.json()["detail"]["error_code"] == "PRINTER_NOT_FOUND"


def test_malformed_csv_returns_400(client, printer_with_mapping):
    r = _post(client, printer_with_mapping.id, body=b"\x00\x01garbage")
    assert r.status_code == 400
    j = r.json()
    assert j["detail"]["error_code"] == "INVALID_CSV"


def test_source_filename_override(client, printer_with_mapping):
    files = {"file": ("autogenerated.csv", io.BytesIO(SAMPLE_CSV), "text/csv")}
    data = {"source_filename": "drive-original.csv"}
    r = client.post(
        f"/printers/{printer_with_mapping.id}/uploads/import",
        files=files,
        data=data,
        headers={"X-API-Key": "test-ingest-key"},
    )
    assert r.status_code == 200
    assert r.json()["source_filename"] == "drive-original.csv"
```

- [ ] **Step 2: Confirm tests fail (route doesn't exist yet)**

Run: `cd backend && pytest tests/integration/test_drive_ingest.py -v`
Expected: all tests fail with 404 (route not registered) or 405.

- [ ] **Step 3: Add the route to `routers/print_jobs.py`**

Add near the top of the file, after the existing imports:

```python
from fastapi import Form
from fastapi.responses import JSONResponse

from app.auth.api_key import require_ingest_api_key
from app.services.csv_import_service import (
    ImportError as CsvImportError,
    import_csv_for_printer,
)
```

Then add the new route (place it after `upload_csv` and before `list_uploads`):

```python
@router.post("/import", dependencies=[Depends(require_ingest_api_key)])
async def import_csv_headless(
    printer_id: int,
    file: UploadFile = File(...),
    source_filename: str | None = Form(default=None),
    db: Session = Depends(get_db),
):
    """Headless CSV import for n8n/external pushers. API-key-authenticated."""
    if not file.filename or not file.filename.lower().endswith(".csv"):
        return JSONResponse(
            status_code=400,
            content={
                "status": "error",
                "error_code": "INVALID_CSV",
                "message": "Only .csv files are accepted",
                "details": [],
                "source_filename": source_filename or (file.filename or ""),
            },
        )

    raw = await file.read()
    if len(raw) > MAX_BYTES:
        return JSONResponse(
            status_code=400,
            content={
                "status": "error",
                "error_code": "INVALID_CSV",
                "message": f"File exceeds {settings.max_csv_upload_size_mb} MB limit",
                "details": [],
                "source_filename": source_filename or file.filename,
            },
        )

    effective_name = source_filename or file.filename

    try:
        result = import_csv_for_printer(
            db=db,
            printer_id=printer_id,
            raw_bytes=raw,
            filename=effective_name,
            source=UploadSource.automated.value,
            uploaded_by_user_id=None,
        )
    except CsvImportError as e:
        status_code = {
            "INVALID_CSV": 400,
            "COLUMN_MAPPING_MISSING": 400,
            "PRINTER_NOT_FOUND": 404,
        }.get(e.error_code, 500)
        return JSONResponse(
            status_code=status_code,
            content={
                "status": "error",
                "error_code": e.error_code,
                "message": e.message,
                "details": e.details,
                "source_filename": effective_name,
            },
        )

    return {
        "status": "success",
        "batch_id": result.batch_id,
        "printer_id": result.printer_id,
        "rows_total": result.rows_total,
        "rows_imported": result.rows_imported,
        "rows_skipped": result.rows_skipped,
        "source_filename": effective_name,
    }
```

- [ ] **Step 4: Run integration tests and confirm 7/7 pass**

Run: `cd backend && pytest tests/integration/test_drive_ingest.py -v`
Expected: 7/7 PASS.

- [ ] **Step 5: Full suite**

Run: `cd backend && pytest -q`
Expected: every test passes. If anything in `tests/unit/test_cost_calc.py` regresses, you broke a helper move in Task 2 — revisit it.

- [ ] **Step 6: Commit**

```bash
git add backend/app/routers/print_jobs.py backend/tests/integration/test_drive_ingest.py
git commit -m "feat(ingest): add POST /printers/{id}/uploads/import endpoint"
```

---

## Task 5 — Manual end-to-end verification with curl

This task has no code — it proves the endpoint behaves as the n8n flow will expect, against a running app. **Do not skip.**

- [ ] **Step 1: Set `INGEST_API_KEY` in `.env`**

Add to `backend/.env` (or the project-root `.env` if that is what `config.py` resolves):

```
INGEST_API_KEY=local-dev-ingest-key
```

Restart the backend so the new setting is picked up.

- [ ] **Step 2: Pick a real printer ID with a column mapping**

Use the UI or `psql` to find an existing printer ID that has `column_mapping` configured. Note it as `<PID>`.

- [ ] **Step 3: Happy path**

```bash
curl -i -X POST http://localhost:8000/printers/<PID>/uploads/import \
  -H "X-API-Key: local-dev-ingest-key" \
  -F "file=@/path/to/real-sample.csv" \
  -F "source_filename=real-sample.csv"
```

Expected: HTTP 200; JSON body with `status: success`, a `batch_id`, and `rows_imported > 0`.

- [ ] **Step 4: Duplicate re-post**

Re-run the exact same command. Expected: HTTP 200, `rows_imported: 0`, `rows_skipped == rows_total` of the file.

- [ ] **Step 5: Wrong key**

```bash
curl -i -X POST http://localhost:8000/printers/<PID>/uploads/import \
  -H "X-API-Key: WRONG" \
  -F "file=@/path/to/real-sample.csv"
```

Expected: HTTP 401, body `{"detail":{"error_code":"UNAUTHORIZED",...}}`.

- [ ] **Step 6: Bad printer ID**

```bash
curl -i -X POST http://localhost:8000/printers/9999999/uploads/import \
  -H "X-API-Key: local-dev-ingest-key" \
  -F "file=@/path/to/real-sample.csv"
```

Expected: HTTP 404 with `error_code: PRINTER_NOT_FOUND`.

- [ ] **Step 7: Garbage file**

```bash
echo "not a csv" > /tmp/garbage.bin
curl -i -X POST http://localhost:8000/printers/<PID>/uploads/import \
  -H "X-API-Key: local-dev-ingest-key" \
  -F "file=@/tmp/garbage.bin;filename=bad.csv"
```

Expected: HTTP 400 with `error_code: INVALID_CSV` and a populated `message`.

- [ ] **Step 8: Confirm batches list shows the new uploads**

Either through the UI's Upload History or via `GET /printers/<PID>/uploads`, verify the rows from Steps 3 and 4 appear and that their `source` is `automated`.

- [ ] **Step 9: Commit nothing, but report results**

No code change in this task. Once all eight verification steps pass, the endpoint is ready for the n8n side. Tell the user the endpoint is verified and ask for the green light to push the branch (per their earlier instruction to only push when they say).

---

## Out of Scope (do not implement in this plan)

- The n8n workflow itself (Drive trigger, file moves, error-log file creation). The endpoint is the contract; n8n is configured separately and outside this repo.
- Per-printer ingest tokens, per-call audit log, rate limiting. Trial scope.
- A UI surface to monitor automated batches separately from manual ones.

## Spec coverage check

- ✅ New endpoint `POST /printers/{printer_id}/uploads/import` — Task 4.
- ✅ X-API-Key auth via `INGEST_API_KEY` — Tasks 1 (config) + 3 (dependency).
- ✅ Structured success / error JSON contract — Task 4.
- ✅ Reuses existing import pipeline + dedup — Task 2 (extract) + Task 4 (call).
- ✅ `UploadSource.automated` for traceability — Task 1.
- ✅ Manual upload path unchanged — Task 2 Step 6 (manual smoke) + Task 4 Step 5 (full suite).
- ✅ Manual verification of the n8n contract — Task 5.
