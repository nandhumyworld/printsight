"""Print jobs router — CSV upload and job listing."""

from __future__ import annotations

import io
import logging
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

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
    p = db.query(Printer).filter(Printer.id == printer_id, Printer.owner_id == owner_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="Printer not found")
    return p


def _parse_int(val: Any, default: int = 0) -> int:
    try:
        return int(float(str(val))) if val is not None and str(val).strip() != "" else default
    except (ValueError, TypeError):
        return default


def _parse_decimal(val: Any, default: Decimal = Decimal("0")) -> Decimal:
    try:
        return Decimal(str(val)) if val is not None and str(val).strip() != "" else default
    except Exception:
        return default


_COVERAGE_MAX = Decimal("9999.9999")


def _parse_coverage(val: Any) -> Decimal | None:
    """Parse a coverage decimal and clamp to Numeric(8,4) range. Returns None if unparseable."""
    if val is None or str(val).strip() in ("", "nan", "none"):
        return None
    try:
        d = Decimal(str(val).strip())
        if d < 0:
            return None
        if d > _COVERAGE_MAX:
            return _COVERAGE_MAX
        return d
    except Exception:
        return None


def _parse_dt(val: Any) -> datetime | None:
    if val is None or str(val).strip() in ("", "nan", "NaT"):
        return None
    try:
        return pd.Timestamp(val).to_pydatetime().replace(tzinfo=timezone.utc)
    except Exception:
        return None


def _col(row: pd.Series, mapping: dict, key: str, default: Any = None) -> Any:
    """Get value using column mapping, falling back to the key itself."""
    col_name = mapping.get(key, key)
    if col_name in row.index:
        return row[col_name]
    if key in row.index:
        return row[key]
    return default


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


def _parse_bool(val: Any) -> bool:
    """Convert duplex-style strings to boolean. 'None'/''/0 → False, anything else → True."""
    if val is None:
        return False
    s = str(val).strip().lower()
    return s not in ("", "none", "no", "false", "0", "nan")


def _str_or_none(val: Any) -> str | None:
    s = str(val).strip() if val is not None else ""
    return s if s and s.lower() not in ("nan", "none") else None


import json as _json_upload  # noqa: E402
from fastapi.responses import StreamingResponse as _StreamingResponseUpload  # noqa: E402

_UPLOAD_BATCH = 500


def _build_job(row, mapping, printer_id, batch_id) -> PrintJob:
    """Build a PrintJob ORM object from a CSV row (no DB ops)."""
    job_id_raw = _col(row, mapping, "job_id") or _col(row, mapping, "jobid") or _col(row, mapping, "id")
    job_id = str(job_id_raw).strip()
    recorded_at = _parse_dt(
        _col(row, mapping, "recorded_at")
        or _col(row, mapping, "printed_at")
        or _col(row, mapping, "date")
    )
    status_val = _str_or_none(_col(row, mapping, "status", "")) or ""
    color_pages = _parse_int(_col(row, mapping, "color_pages", 0))
    bw_pages = _parse_int(_col(row, mapping, "bw_pages", 0))
    printed_pages = _parse_int(_col(row, mapping, "printed_pages") or _col(row, mapping, "pages", 0))
    if printed_pages == 0:
        printed_pages = color_pages + bw_pages
    pw = _col(row, mapping, "paper_width_mm")
    pl = _col(row, mapping, "paper_length_mm")
    return PrintJob(
        printer_id=printer_id, upload_batch_id=batch_id, job_id=job_id,
        job_name=_str_or_none(_col(row, mapping, "job_name", "")),
        status=_str_or_none(status_val),
        owner_name=_str_or_none(_col(row, mapping, "owner_name", "")),
        recorded_at=recorded_at,
        arrived_at=_parse_dt(_col(row, mapping, "arrived_at")),
        printed_at=_parse_dt(_col(row, mapping, "printed_at")),
        color_mode=_str_or_none(_col(row, mapping, "color_mode", "")),
        paper_type=_str_or_none(_col(row, mapping, "paper_type", "")),
        paper_size=_str_or_none(_col(row, mapping, "paper_size", "")),
        paper_width_mm=_parse_decimal(pw) if pw and str(pw).strip() not in ("", "0", "nan") else None,
        paper_length_mm=_parse_decimal(pl) if pl and str(pl).strip() not in ("", "0", "nan") else None,
        is_duplex=_parse_bool(_col(row, mapping, "is_duplex")),
        copies=_parse_int(_col(row, mapping, "copies", 1)) or 1,
        input_pages=_parse_int(_col(row, mapping, "input_pages", 0)),
        printed_pages=printed_pages, color_pages=color_pages, bw_pages=bw_pages,
        specialty_pages=_parse_int(_col(row, mapping, "specialty_pages", 0)),
        gold_pages=_parse_int(_col(row, mapping, "gold_pages", 0)),
        silver_pages=_parse_int(_col(row, mapping, "silver_pages", 0)),
        clear_pages=_parse_int(_col(row, mapping, "clear_pages", 0)),
        white_pages=_parse_int(_col(row, mapping, "white_pages", 0)),
        texture_pages=_parse_int(_col(row, mapping, "texture_pages", 0)),
        pink_pages=_parse_int(_col(row, mapping, "pink_pages", 0)),
        blank_pages=_parse_int(_col(row, mapping, "blank_pages", 0)),
        printed_sheets=_parse_int(_col(row, mapping, "printed_sheets", 0)),
        waste_sheets=_parse_int(_col(row, mapping, "waste_sheets", 0)),
        error_info=_str_or_none(_col(row, mapping, "error_info", "")),
        is_waste=status_val.lower() in ("failed", "cancelled", "canceled", "error"),
        sub_id=_str_or_none(_col(row, mapping, "sub_id", "")),
        jdf_job_id=_str_or_none(_col(row, mapping, "jdf_job_id", "")),
        jdf_job_part_id=_str_or_none(_col(row, mapping, "jdf_job_part_id", "")),
        logical_printer=_str_or_none(_col(row, mapping, "logical_printer", "")),
        template=_str_or_none(_col(row, mapping, "template", "")),
        imposition_settings=_str_or_none(_col(row, mapping, "imposition_settings", "")),
        media_name=_str_or_none(_col(row, mapping, "media_name", "")),
        paper_tray=_str_or_none(_col(row, mapping, "paper_tray", "")),
        print_collation=_str_or_none(_col(row, mapping, "print_collation", "")),
        imposed_pages=_parse_int(_col(row, mapping, "imposed_pages")) or None,
        last_printed_page=_str_or_none(_col(row, mapping, "last_printed_page", "")),
        banner_sheet=_str_or_none(_col(row, mapping, "banner_sheet", "")),
        change_output_destination=_str_or_none(_col(row, mapping, "change_output_destination", "")),
        account=_str_or_none(_col(row, mapping, "account", "")),
        comments=_str_or_none(_col(row, mapping, "comments", "")),
        folder=_str_or_none(_col(row, mapping, "folder", "")),
        tag=_str_or_none(_col(row, mapping, "tag", "")),
        conversion_start_at=_parse_dt(_col(row, mapping, "conversion_start_at")),
        conversion_elapsed=_str_or_none(_col(row, mapping, "conversion_elapsed", "")),
        rip_start_at=_parse_dt(_col(row, mapping, "rip_start_at")),
        rip_elapsed=_str_or_none(_col(row, mapping, "rip_elapsed", "")),
        rasterization_start_at=_parse_dt(_col(row, mapping, "rasterization_start_at")),
        rasterization_elapsed=_str_or_none(_col(row, mapping, "rasterization_elapsed", "")),
        printing_start_at=_parse_dt(_col(row, mapping, "printing_start_at")),
        printing_elapsed=_str_or_none(_col(row, mapping, "printing_elapsed", "")),
        pa_pages=_parse_int(_col(row, mapping, "pa_pages", 0)),
        gold_6_pages=_parse_int(_col(row, mapping, "gold_6_pages", 0)),
        silver_6_pages=_parse_int(_col(row, mapping, "silver_6_pages", 0)),
        white_6_pages=_parse_int(_col(row, mapping, "white_6_pages", 0)),
        pink_6_pages=_parse_int(_col(row, mapping, "pink_6_pages", 0)),
        coverage_k=_parse_coverage(_col(row, mapping, "coverage_k")),
        coverage_c=_parse_coverage(_col(row, mapping, "coverage_c")),
        coverage_m=_parse_coverage(_col(row, mapping, "coverage_m")),
        coverage_y=_parse_coverage(_col(row, mapping, "coverage_y")),
        coverage_gld_1=_parse_coverage(_col(row, mapping, "coverage_gld_1")),
        coverage_slv_1=_parse_coverage(_col(row, mapping, "coverage_slv_1")),
        coverage_clr_1=_parse_coverage(_col(row, mapping, "coverage_clr_1")),
        coverage_wht_1=_parse_coverage(_col(row, mapping, "coverage_wht_1")),
        coverage_cr_1=_parse_coverage(_col(row, mapping, "coverage_cr_1")),
        coverage_p_1=_parse_coverage(_col(row, mapping, "coverage_p_1")),
        coverage_pa_1=_parse_coverage(_col(row, mapping, "coverage_pa_1")),
        coverage_gld_6=_parse_coverage(_col(row, mapping, "coverage_gld_6")),
        coverage_slv_6=_parse_coverage(_col(row, mapping, "coverage_slv_6")),
        coverage_wht_6=_parse_coverage(_col(row, mapping, "coverage_wht_6")),
        coverage_p_6=_parse_coverage(_col(row, mapping, "coverage_p_6")),
        coverage_est_k=_parse_coverage(_col(row, mapping, "coverage_est_k")),
        coverage_est_c=_parse_coverage(_col(row, mapping, "coverage_est_c")),
        coverage_est_m=_parse_coverage(_col(row, mapping, "coverage_est_m")),
        coverage_est_y=_parse_coverage(_col(row, mapping, "coverage_est_y")),
        coverage_est_gld_1=_parse_coverage(_col(row, mapping, "coverage_est_gld_1")),
        coverage_est_slv_1=_parse_coverage(_col(row, mapping, "coverage_est_slv_1")),
        coverage_est_clr_1=_parse_coverage(_col(row, mapping, "coverage_est_clr_1")),
        coverage_est_wht_1=_parse_coverage(_col(row, mapping, "coverage_est_wht_1")),
        coverage_est_cr_1=_parse_coverage(_col(row, mapping, "coverage_est_cr_1")),
        coverage_est_p_1=_parse_coverage(_col(row, mapping, "coverage_est_p_1")),
        coverage_est_pa_1=_parse_coverage(_col(row, mapping, "coverage_est_pa_1")),
        coverage_est_gld_6=_parse_coverage(_col(row, mapping, "coverage_est_gld_6")),
        coverage_est_slv_6=_parse_coverage(_col(row, mapping, "coverage_est_slv_6")),
        coverage_est_wht_6=_parse_coverage(_col(row, mapping, "coverage_est_wht_6")),
        coverage_est_p_6=_parse_coverage(_col(row, mapping, "coverage_est_p_6")),
        computed_paper_cost=Decimal("0"),
        computed_toner_cost=Decimal("0"),
        computed_total_cost=Decimal("0"),
    )


@router.post("")
async def upload_csv(
    printer_id: int,
    current_user: CurrentUser,
    db: Session = Depends(get_db),
    file: UploadFile = File(...),
):
    """Upload CSV and stream SSE import progress events."""
    p = _get_printer_or_403(db, printer_id, current_user.id)

    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only .csv files are accepted")

    raw = await file.read()
    if len(raw) > MAX_BYTES:
        raise HTTPException(status_code=400, detail=f"File exceeds {settings.max_csv_upload_size_mb} MB limit")

    try:
        df = pd.read_csv(io.BytesIO(raw), dtype=str, keep_default_na=False)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Could not parse CSV: {exc}")

    df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]
    mapping: dict = {k.lower(): v.strip().lower().replace(" ", "_") for k, v in (p.column_mapping or {}).items()}
    filename = file.filename
    user_id = current_user.id
    total_rows = len(df)

    def _evt(payload: dict) -> str:
        return f"data: {_json_upload.dumps(payload)}\n\n"

    def generate():
        # Create the upload batch record
        session = _SessionLocal()
        try:
            batch = UploadBatch(
                printer_id=printer_id, uploaded_by_user_id=user_id,
                source=UploadSource.manual, filename=filename,
                rows_total=total_rows, status=UploadStatus.processing,
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

        yield _evt({"done": 0, "total": total_rows})

        imported = 0
        skipped: list[dict] = []
        batch_keys: set = set()

        # Process in batches of _UPLOAD_BATCH rows
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

            # Insert this chunk in one commit
            if jobs_to_add:
                session = _SessionLocal()
                try:
                    session.add_all(jobs_to_add)
                    session.commit()
                    imported += len(jobs_to_add)
                except Exception as e:
                    session.rollback()
                    chunk_skipped.append({"row_number": 0, "reason": f"DB error: {str(e)[:80]}"})
                finally:
                    session.close()

            skipped.extend(chunk_skipped)
            done_rows = min(chunk_start + _UPLOAD_BATCH, total_rows)
            yield _evt({"done": done_rows, "total": total_rows})

        # Finalise the batch record
        session = _SessionLocal()
        try:
            b = session.query(UploadBatch).filter(UploadBatch.id == batch_id).first()
            if b:
                b.rows_imported = imported
                b.rows_skipped = len(skipped)
                b.skipped_details = skipped
                b.status = UploadStatus.completed
                session.commit()
        finally:
            session.close()

        yield _evt({
            "done": total_rows, "total": total_rows, "complete": True,
            "batch_id": batch_id, "rows_total": total_rows,
            "rows_imported": imported, "rows_skipped": len(skipped),
            "skipped_details": skipped[:20],
            "message": f"Imported {imported} jobs, skipped {len(skipped)}",
        })

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
    p = db.query(Printer).filter(Printer.id == printer_id, Printer.owner_id == current_user.id).first()
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
