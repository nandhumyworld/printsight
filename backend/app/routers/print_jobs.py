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
from app.models.printer import Printer
from app.models.toner import Toner, TonerReplacementLog
from app.models.upload import PrintJob, UploadBatch, UploadSource, UploadStatus

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


@router.post("")
async def upload_csv(
    printer_id: int,
    current_user: CurrentUser,
    db: Session = Depends(get_db),
    file: UploadFile = File(...),
):
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

    # Build mapping: {field_key: normalized_csv_column}
    mapping: dict = {k.lower(): v.strip().lower().replace(" ", "_") for k, v in (p.column_mapping or {}).items()}

    batch = UploadBatch(
        printer_id=printer_id,
        uploaded_by_user_id=current_user.id,
        source=UploadSource.manual,
        filename=file.filename,
        rows_total=len(df),
        status=UploadStatus.processing,
    )
    db.add(batch)
    db.flush()

    # Pre-load existing (job_id, recorded_at) pairs to check duplicates without per-row DB queries
    existing_keys: set[tuple] = set(
        db.query(PrintJob.job_id, PrintJob.recorded_at)
        .filter(PrintJob.printer_id == printer_id)
        .all()
    )
    # Track keys added in this batch (in-session duplicates)
    batch_keys: set[tuple] = set()

    skipped: list[dict] = []
    imported = 0

    for idx, row in df.iterrows():
        row_num = int(str(idx)) + 2  # 1-indexed + header

        # Resolve job_id
        job_id_raw = _col(row, mapping, "job_id") or _col(row, mapping, "jobid") or _col(row, mapping, "id")
        if not job_id_raw or str(job_id_raw).strip() in ("", "nan"):
            skipped.append({"row_number": row_num, "reason": "Missing job_id"})
            continue

        job_id = str(job_id_raw).strip()

        # Recorded at — try multiple fallbacks
        recorded_at = _parse_dt(
            _col(row, mapping, "recorded_at")
            or _col(row, mapping, "printed_at")
            or _col(row, mapping, "date")
        )

        # Duplicate check: (job_id, recorded_at) must be unique per printer
        dup_key = (job_id, recorded_at)
        if dup_key in existing_keys or dup_key in batch_keys:
            skipped.append({"row_number": row_num, "reason": f"Duplicate job_id={job_id} at {recorded_at}"})
            continue

        status_val = _str_or_none(_col(row, mapping, "status", "")) or ""
        is_waste = status_val.lower() in ("failed", "cancelled", "canceled", "error")

        color_pages = _parse_int(_col(row, mapping, "color_pages", 0))
        bw_pages = _parse_int(_col(row, mapping, "bw_pages", 0))
        printed_pages = _parse_int(_col(row, mapping, "printed_pages") or _col(row, mapping, "pages", 0))
        if printed_pages == 0:
            printed_pages = color_pages + bw_pages

        # paper dimensions — may be mapped
        pw = _col(row, mapping, "paper_width_mm")
        pl = _col(row, mapping, "paper_length_mm")

        job = PrintJob(
            printer_id=printer_id,
            upload_batch_id=batch.id,
            job_id=job_id,
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
            printed_pages=printed_pages,
            color_pages=color_pages,
            bw_pages=bw_pages,
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
            is_waste=is_waste,
            # Extended metadata
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
            # Timing
            conversion_start_at=_parse_dt(_col(row, mapping, "conversion_start_at")),
            conversion_elapsed=_str_or_none(_col(row, mapping, "conversion_elapsed", "")),
            rip_start_at=_parse_dt(_col(row, mapping, "rip_start_at")),
            rip_elapsed=_str_or_none(_col(row, mapping, "rip_elapsed", "")),
            rasterization_start_at=_parse_dt(_col(row, mapping, "rasterization_start_at")),
            rasterization_elapsed=_str_or_none(_col(row, mapping, "rasterization_elapsed", "")),
            printing_start_at=_parse_dt(_col(row, mapping, "printing_start_at")),
            printing_elapsed=_str_or_none(_col(row, mapping, "printing_elapsed", "")),
            # Specialty toner pages
            pa_pages=_parse_int(_col(row, mapping, "pa_pages", 0)),
            gold_6_pages=_parse_int(_col(row, mapping, "gold_6_pages", 0)),
            silver_6_pages=_parse_int(_col(row, mapping, "silver_6_pages", 0)),
            white_6_pages=_parse_int(_col(row, mapping, "white_6_pages", 0)),
            pink_6_pages=_parse_int(_col(row, mapping, "pink_6_pages", 0)),
            # Raster coverage CMYK
            coverage_k=_parse_decimal(_col(row, mapping, "coverage_k")) or None,
            coverage_c=_parse_decimal(_col(row, mapping, "coverage_c")) or None,
            coverage_m=_parse_decimal(_col(row, mapping, "coverage_m")) or None,
            coverage_y=_parse_decimal(_col(row, mapping, "coverage_y")) or None,
            # Raster coverage specialty #1
            coverage_gld_1=_parse_decimal(_col(row, mapping, "coverage_gld_1")) or None,
            coverage_slv_1=_parse_decimal(_col(row, mapping, "coverage_slv_1")) or None,
            coverage_clr_1=_parse_decimal(_col(row, mapping, "coverage_clr_1")) or None,
            coverage_wht_1=_parse_decimal(_col(row, mapping, "coverage_wht_1")) or None,
            coverage_cr_1=_parse_decimal(_col(row, mapping, "coverage_cr_1")) or None,
            coverage_p_1=_parse_decimal(_col(row, mapping, "coverage_p_1")) or None,
            coverage_pa_1=_parse_decimal(_col(row, mapping, "coverage_pa_1")) or None,
            # Raster coverage specialty #6
            coverage_gld_6=_parse_decimal(_col(row, mapping, "coverage_gld_6")) or None,
            coverage_slv_6=_parse_decimal(_col(row, mapping, "coverage_slv_6")) or None,
            coverage_wht_6=_parse_decimal(_col(row, mapping, "coverage_wht_6")) or None,
            coverage_p_6=_parse_decimal(_col(row, mapping, "coverage_p_6")) or None,
            # Raster coverage estimation CMYK
            coverage_est_k=_parse_decimal(_col(row, mapping, "coverage_est_k")) or None,
            coverage_est_c=_parse_decimal(_col(row, mapping, "coverage_est_c")) or None,
            coverage_est_m=_parse_decimal(_col(row, mapping, "coverage_est_m")) or None,
            coverage_est_y=_parse_decimal(_col(row, mapping, "coverage_est_y")) or None,
            # Raster coverage estimation specialty #1
            coverage_est_gld_1=_parse_decimal(_col(row, mapping, "coverage_est_gld_1")) or None,
            coverage_est_slv_1=_parse_decimal(_col(row, mapping, "coverage_est_slv_1")) or None,
            coverage_est_clr_1=_parse_decimal(_col(row, mapping, "coverage_est_clr_1")) or None,
            coverage_est_wht_1=_parse_decimal(_col(row, mapping, "coverage_est_wht_1")) or None,
            coverage_est_cr_1=_parse_decimal(_col(row, mapping, "coverage_est_cr_1")) or None,
            coverage_est_p_1=_parse_decimal(_col(row, mapping, "coverage_est_p_1")) or None,
            coverage_est_pa_1=_parse_decimal(_col(row, mapping, "coverage_est_pa_1")) or None,
            # Raster coverage estimation specialty #6
            coverage_est_gld_6=_parse_decimal(_col(row, mapping, "coverage_est_gld_6")) or None,
            coverage_est_slv_6=_parse_decimal(_col(row, mapping, "coverage_est_slv_6")) or None,
            coverage_est_wht_6=_parse_decimal(_col(row, mapping, "coverage_est_wht_6")) or None,
            coverage_est_p_6=_parse_decimal(_col(row, mapping, "coverage_est_p_6")) or None,
            computed_paper_cost=Decimal("0"),
            computed_toner_cost=Decimal("0"),
            computed_total_cost=Decimal("0"),
        )

        try:
            db.add(job)
            db.flush()  # flush per row so constraint errors are caught individually
            batch_keys.add(dup_key)
            imported += 1
        except Exception as e:
            db.rollback()
            # Re-flush the batch record after rollback
            db.add(batch)
            db.flush()
            skipped.append({"row_number": row_num, "reason": f"DB error: {str(e)[:80]}"})

    batch.rows_imported = imported
    batch.rows_skipped = len(skipped)
    batch.skipped_details = skipped
    batch.status = UploadStatus.completed
    db.commit()

    return {
        "data": {
            "batch_id": batch.id,
            "rows_total": batch.rows_total,
            "rows_imported": imported,
            "rows_skipped": len(skipped),
            "skipped_details": skipped[:20],
        },
        "message": f"Imported {imported} jobs, skipped {len(skipped)}",
    }


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
