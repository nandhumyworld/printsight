"""Shared CSV import core used by manual SSE upload and headless API.

Extracted from routers/print_jobs.py to allow two entry points to share the
same parsing, dedup, and batched-insert logic. No behaviour change versus
the original handler; only the surface (sync function vs generator) differs.
"""

from __future__ import annotations

import io
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Callable, Optional

import pandas as pd
from app.database import SessionLocal
from app.models.printer import Printer
from app.models.upload import (
    PrintJob,
    UploadBatch,
    UploadSource,
    UploadStatus,
)
from app.services.cost_calc import apply_cost_to_job, compute_job_cost, match_paper_for_job

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


def _parse_bool(val: Any) -> bool:
    """Convert duplex-style strings to boolean. 'None'/''/0 → False, anything else → True."""
    if val is None:
        return False
    s = str(val).strip().lower()
    return s not in ("", "none", "no", "false", "0", "nan")


def _str_or_none(val: Any) -> str | None:
    s = str(val).strip() if val is not None else ""
    return s if s and s.lower() not in ("nan", "none") else None


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
        computed_paper_cost=Decimal("0"),
        computed_toner_cost=Decimal("0"),
        computed_total_cost=Decimal("0"),
    )


# --- Public entry point ------------------------------------------------------

def import_csv_for_printer(
    *,
    printer_id: int,
    raw_bytes: bytes,
    filename: str,
    source: str,
    uploaded_by_user_id: Optional[int],
    progress_callback: Optional[Callable[[int, int], None]] = None,
) -> ImportResult:
    """Run the full CSV → DB import pipeline for one printer.

    Owns all of its own DB sessions via SessionLocal so it can be safely
    invoked from a background thread (the manual SSE upload runs the service
    on a worker thread; the request session is not thread-safe).

    Raises ImportError on validation/precondition failures *before* any DB write.
    On success, persists an UploadBatch + PrintJob rows and returns ImportResult.
    """
    # 1. Resolve printer / mapping.
    # Use our own short-lived session — this function may be called from a
    # background thread (e.g. the SSE shim), and the caller's `db` session is
    # not thread-safe. We snapshot the column_mapping into a plain dict so the
    # rest of the pipeline does not need ORM-attached state.
    _lookup = SessionLocal()
    try:
        printer = _lookup.query(Printer).filter(Printer.id == printer_id).first()
        if not printer:
            raise ImportError("PRINTER_NOT_FOUND", f"Printer {printer_id} not found")
        if not printer.column_mapping:
            raise ImportError(
                "COLUMN_MAPPING_MISSING",
                f"Printer {printer_id} has no column_mapping configured",
            )
        printer_column_mapping = dict(printer.column_mapping)
    finally:
        _lookup.close()

    # Cost inputs — loaded once, detached, reused across all chunks.
    from sqlalchemy.orm import joinedload
    from app.models.paper import Paper
    from app.models.toner import Toner

    _cost_setup = SessionLocal()
    try:
        toners = (
            _cost_setup.query(Toner)
            .options(joinedload(Toner.replacement_logs))
            .filter(Toner.printer_id == printer_id)
            .all()
        )
        papers = (
            _cost_setup.query(Paper)
            .join(Paper.printer_links)
            .filter_by(printer_id=printer_id)
            .all()
        )
        _cost_setup.expunge_all()
    finally:
        _cost_setup.close()

    # 2. Parse CSV (no DB writes yet)
    # Reject obvious binary garbage (null bytes) up front — pandas silently
    # accepts them and yields an empty/bogus frame, which would otherwise
    # masquerade as a "successful" zero-row import.
    if b"\x00" in raw_bytes:
        raise ImportError("INVALID_CSV", "File contains null bytes; not a valid text CSV")
    try:
        df = pd.read_csv(io.BytesIO(raw_bytes), dtype=str, keep_default_na=False)
    except Exception as exc:
        raise ImportError("INVALID_CSV", f"Could not parse CSV: {exc}") from exc

    df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]
    mapping = {k.lower(): v.strip().lower().replace(" ", "_") for k, v in printer_column_mapping.items()}
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

        costed = 0
        zero_toner = 0
        for job in jobs_to_add:
            try:
                matched = match_paper_for_job(job, papers)
                job.matched_paper_id = matched.id if matched else None
                result = compute_job_cost(job, toners=toners, matched_paper=matched)
                apply_cost_to_job(job, result)
                costed += 1
                if result["toner_cost"] == 0:
                    zero_toner += 1
            except Exception as job_err:
                logger.warning(
                    "cost compute failed printer=%s job_id=%s: %s",
                    printer_id, getattr(job, "job_id", "?"), job_err,
                )

        if jobs_to_add:
            chunk_session = SessionLocal()
            try:
                chunk_session.add_all(jobs_to_add)
                chunk_session.commit()
                imported += len(jobs_to_add)
                logger.info(
                    "csv_import costed chunk printer=%s batch=%s jobs=%d zero_toner=%d",
                    printer_id, batch_id, costed, zero_toner,
                )
            except Exception as e:
                chunk_session.rollback()
                logger.error(
                    "csv_import chunk insert failed at offset %d for printer %d: %s",
                    chunk_start, printer_id, e,
                )
                chunk_skipped.append({
                    "row_number": 0,
                    "reason": f"DB error in chunk starting row {chunk_start + 2}: {str(e)[:80]}",
                })
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
