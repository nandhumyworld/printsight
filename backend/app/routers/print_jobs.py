"""Print jobs router — CSV upload and job listing."""

from __future__ import annotations

import io
import logging
from datetime import datetime, timezone
from decimal import Decimal

import pandas as pd
from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from sqlalchemy.orm import Session

from app.auth.deps import CurrentUser
from app.config import settings
from app.database import get_db
from app.models.paper import Paper
from app.models.printer import Printer
from app.models.toner import Toner, TonerReplacementLog
from app.models.upload import PrintJob, UploadBatch, UploadSource, UploadStatus
from app.services.cost_calc import compute_job_cost, match_paper_for_job  # noqa: F401 (used in recompute)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/printers/{printer_id}/uploads", tags=["print-jobs"])

REQUIRED_COLS = {"job_id"}  # minimal required columns for MVP
MAX_BYTES = settings.max_csv_upload_size_mb * 1024 * 1024


def _get_printer_or_403(db: Session, printer_id: int, owner_id: int) -> Printer:
    p = db.query(Printer).filter(Printer.id == printer_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="Printer not found")
    return p


# Known field aliases for fuzzy mapping suggestions
_FIELD_ALIASES: dict[str, list[str]] = {
    "job_id":        ["jobid", "id", "job_number", "print_job_id"],
    "job_name":      ["name", "document", "doc_name", "file_name", "filename", "title"],
    "recorded_at":   ["date", "datetime", "time", "timestamp", "print_date", "printed_date"],
    "printed_at":    ["printed_time", "completion_time"],
    "arrived_at":    ["arrival", "arrived_time", "submit_time"],
    "status":        ["state", "result", "job_status", "print_status"],
    "owner_name":    ["user", "username", "user_name", "submitted_by", "owner", "sender"],
    "color_mode":    ["colour", "colour_mode", "color", "print_mode", "mode"],
    "paper_type":    ["paper", "media", "media_type", "stock", "paper_stock"],
    "paper_size":    ["size", "media_size", "page_size", "format"],
    "copies":        ["copy", "num_copies", "quantity"],
    "printed_pages": ["pages", "total_pages", "page_count", "sheets_printed"],
    "color_pages":   ["colour_pages", "color_count", "colour_count"],
    "bw_pages":      ["black_pages", "mono_pages", "bw_count", "greyscale_pages"],
    "printed_sheets":["sheets", "sheet_count"],
    "waste_sheets":  ["wasted_sheets", "failed_sheets"],
    "is_duplex":     ["duplex", "double_sided", "two_sided"],
}


def _suggest_mapping(detected_cols: list[str]) -> dict[str, str]:
    """Return {field_name: detected_column} for best-guess matches."""
    col_lower = {c.lower().replace(" ", "_"): c for c in detected_cols}
    mapping: dict[str, str] = {}

    for field, aliases in _FIELD_ALIASES.items():
        # 1. Exact match on field name
        if field in col_lower:
            mapping[field] = col_lower[field]
            continue
        # 2. Alias exact match
        for alias in aliases:
            if alias in col_lower:
                mapping[field] = col_lower[alias]
                break
        else:
            # 3. Substring match — column contains field key or alias
            for col_key, col_orig in col_lower.items():
                if field in col_key or any(a in col_key for a in aliases):
                    mapping[field] = col_orig
                    break

    return mapping


@router.post("/preview")
async def preview_csv(
    printer_id: int,
    current_user: CurrentUser,
    db: Session = Depends(get_db),
    file: UploadFile = File(...),
):
    """Parse CSV and return column detection + first 5 rows. Does NOT save anything."""
    _get_printer_or_403(db, printer_id, current_user.id)

    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only .csv files are accepted")

    raw = await file.read()
    if len(raw) > MAX_BYTES:
        raise HTTPException(status_code=400, detail=f"File exceeds {settings.max_csv_upload_size_mb} MB limit")

    try:
        df = pd.read_csv(io.BytesIO(raw), dtype=str, keep_default_na=False)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Could not parse CSV: {exc}")

    detected_columns = list(df.columns)
    total_rows = len(df)
    preview_rows = df.head(5).to_dict(orient="records")
    suggested_mapping = _suggest_mapping(detected_columns)

    return {
        "data": {
            "detected_columns": detected_columns,
            "suggested_mapping": suggested_mapping,
            "preview_rows": preview_rows,
            "total_rows": total_rows,
        },
        "message": "ok",
    }


import json as _json_upload  # noqa: E402
from fastapi.responses import StreamingResponse as _StreamingResponseUpload  # noqa: E402


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

    _get_printer_or_403(db, printer_id, current_user.id)

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



@router.get("")
async def list_uploads(
    printer_id: int,
    current_user: CurrentUser,
    db: Session = Depends(get_db),
):
    _get_printer_or_403(db, printer_id, current_user.id)
    batches = db.query(UploadBatch).filter(UploadBatch.printer_id == printer_id).order_by(UploadBatch.uploaded_at.desc()).limit(20).all()
    return {
        "data": [
            {
                "id": b.id,
                "filename": b.filename,
                "uploaded_at": b.uploaded_at.isoformat(),
                "rows_total": b.rows_total,
                "rows_imported": b.rows_imported,
                "rows_skipped": b.rows_skipped,
                "status": b.status.value,
            }
            for b in batches
        ],
        "message": "ok",
    }


@router.delete("/clear", status_code=200)
async def clear_all_jobs(
    printer_id: int,
    current_user: CurrentUser,
    db: Session = Depends(get_db),
):
    """Delete ALL print jobs and upload batches for a printer. For testing only."""
    _get_printer_or_403(db, printer_id, current_user.id)
    jobs_deleted = db.query(PrintJob).filter(PrintJob.printer_id == printer_id).delete()
    batches_deleted = db.query(UploadBatch).filter(UploadBatch.printer_id == printer_id).delete()
    db.commit()
    return {"data": {"jobs_deleted": jobs_deleted, "batches_deleted": batches_deleted}, "message": f"Cleared {jobs_deleted} jobs and {batches_deleted} upload batches"}


import json as _json  # noqa: E402

from fastapi.responses import StreamingResponse as _StreamingResponse  # noqa: E402
from pydantic import BaseModel as _BaseModel  # noqa: E402

from app.database import SessionLocal as _SessionLocal  # noqa: E402


class RecomputeRequest(_BaseModel):
    from_date: datetime | None = None
    to_date: datetime | None = None
    batch_id: int | None = None


_RECOMPUTE_BATCH = 500


@router.post("/recompute-costs")
async def recompute_costs(
    printer_id: int,
    current_user: CurrentUser,
    db: Session = Depends(get_db),
    body: RecomputeRequest | None = None,
):
    """Recompute costs in batches, streaming SSE progress events."""
    _get_printer_or_403(db, printer_id, current_user.id)
    body = body or RecomputeRequest()

    # Count total jobs for progress reporting
    q = db.query(PrintJob).filter(PrintJob.printer_id == printer_id)
    if body.from_date:
        q = q.filter(PrintJob.recorded_at >= body.from_date)
    if body.to_date:
        q = q.filter(PrintJob.recorded_at <= body.to_date)
    if body.batch_id:
        q = q.filter(PrintJob.upload_batch_id == body.batch_id)
    total = q.count()

    from_date = body.from_date
    to_date = body.to_date
    batch_id = body.batch_id

    def _event(payload: dict) -> str:
        return f"data: {_json.dumps(payload)}\n\n"

    def generate():
        try:
            yield _event({"done": 0, "total": total})

            # Load papers and toners once — they don't change during recompute
            setup_session = _SessionLocal()
            try:
                from sqlalchemy.orm import joinedload as _joinedload
                papers = (
                    setup_session.query(Paper)
                    .join(Paper.printer_links)
                    .filter_by(printer_id=printer_id)
                    .all()
                )
                toners = (
                    setup_session.query(Toner)
                    .options(_joinedload(Toner.replacement_logs))
                    .filter(Toner.printer_id == printer_id)
                    .all()
                )
                # Detach so they can be used across sessions
                setup_session.expunge_all()
            finally:
                setup_session.close()

            done = 0
            offset = 0
            while True:
                session = _SessionLocal()
                try:
                    bq = session.query(PrintJob).filter(PrintJob.printer_id == printer_id)
                    if from_date:
                        bq = bq.filter(PrintJob.recorded_at >= from_date)
                    if to_date:
                        bq = bq.filter(PrintJob.recorded_at <= to_date)
                    if batch_id:
                        bq = bq.filter(PrintJob.upload_batch_id == batch_id)
                    jobs = bq.order_by(PrintJob.id).offset(offset).limit(_RECOMPUTE_BATCH).all()

                    if not jobs:
                        session.close()
                        break

                    for job in jobs:
                        try:
                            matched = match_paper_for_job(job, papers)
                            job.matched_paper_id = matched.id if matched else None
                            cost_result = compute_job_cost(job, toners=toners, matched_paper=matched)
                            job.computed_paper_cost = Decimal(str(cost_result["paper_cost"]))
                            job.computed_toner_cost = Decimal(str(cost_result["toner_cost"]))
                            job.computed_total_cost = Decimal(str(cost_result["total_cost"]))
                            job.computed_toner_cost_breakdown = cost_result["breakdown"]
                            job.cost_computation_source = cost_result["source"]
                            job.cost_computed_at = datetime.now(timezone.utc)
                        except Exception as job_err:
                            logger.warning("Cost compute failed for job %s: %s", job.id, job_err)

                    session.commit()
                    done += len(jobs)
                    offset += _RECOMPUTE_BATCH
                except Exception as batch_err:
                    logger.error("Recompute batch error at offset %d: %s", offset, batch_err)
                    session.rollback()
                    offset += _RECOMPUTE_BATCH  # skip bad batch
                finally:
                    session.close()

                yield _event({"done": done, "total": total})

            yield _event({"done": total, "total": total, "complete": True})
        except Exception as fatal:
            logger.error("Recompute fatal error: %s", fatal)
            yield _event({"error": str(fatal), "complete": True})

    return _StreamingResponse(generate(), media_type="text/event-stream")


# Separate router for jobs listing
jobs_router = APIRouter(prefix="/printers/{printer_id}/jobs", tags=["print-jobs"])


@jobs_router.get("")
async def list_jobs(
    printer_id: int,
    current_user: CurrentUser,
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    p = db.query(Printer).filter(Printer.id == printer_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="Printer not found")

    q = db.query(PrintJob).filter(PrintJob.printer_id == printer_id).order_by(PrintJob.recorded_at.desc())
    total = q.count()
    jobs = q.offset((page - 1) * per_page).limit(per_page).all()

    return {
        "data": [_job_out(j) for j in jobs],
        "total": total,
        "page": page,
        "per_page": per_page,
        "message": "ok",
    }


def _job_out(j: PrintJob) -> dict:
    return {
        "id": j.id,
        "job_id": j.job_id,
        "job_name": j.job_name,
        "status": j.status,
        "owner_name": j.owner_name,
        "recorded_at": j.recorded_at.isoformat() if j.recorded_at else None,
        "color_pages": j.color_pages,
        "bw_pages": j.bw_pages,
        "printed_pages": j.printed_pages,
        "copies": j.copies,
        "paper_type": j.paper_type,
        "paper_size": j.paper_size,
        "color_mode": j.color_mode,
        "computed_total_cost": float(j.computed_total_cost),
        "is_waste": j.is_waste,
    }
