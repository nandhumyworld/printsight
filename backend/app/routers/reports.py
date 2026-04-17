"""Reports router — filtered job list and CSV export."""

from __future__ import annotations

import csv
import io
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.auth.deps import OwnerUser
from app.database import get_db
from app.models.printer import Printer
from app.models.upload import PrintJob

router = APIRouter(prefix="/reports", tags=["reports"])

SORTABLE = {
    "recorded_at": PrintJob.recorded_at,
    "printed_pages": PrintJob.printed_pages,
    "job_name": PrintJob.job_name,
    "status": PrintJob.status,
}


def _build_query(
    db: Session,
    owner_id: int,
    printer_ids_str: str | None,
    date_from: str | None,
    date_to: str | None,
    status: str,
    search: str | None,
):
    # Resolve printer scope
    all_printer_ids = [
        p.id for p in db.query(Printer.id).filter(Printer.owner_id == owner_id).all()
    ]
    if not all_printer_ids:
        return None

    if printer_ids_str:
        try:
            requested = [int(x.strip()) for x in printer_ids_str.split(",") if x.strip()]
            scoped_ids = [pid for pid in requested if pid in all_printer_ids]
        except ValueError:
            scoped_ids = all_printer_ids
    else:
        scoped_ids = all_printer_ids

    q = db.query(PrintJob).filter(PrintJob.printer_id.in_(scoped_ids))

    if date_from:
        try:
            dt = datetime.fromisoformat(date_from).replace(hour=0, minute=0, second=0, tzinfo=timezone.utc)
            q = q.filter(PrintJob.recorded_at >= dt)
        except ValueError:
            pass

    if date_to:
        try:
            dt = datetime.fromisoformat(date_to).replace(hour=23, minute=59, second=59, tzinfo=timezone.utc)
            q = q.filter(PrintJob.recorded_at <= dt)
        except ValueError:
            pass

    if status and status != "all":
        q = q.filter(PrintJob.status == status)

    if search:
        term = f"%{search}%"
        q = q.filter(
            or_(
                PrintJob.job_name.ilike(term),
                PrintJob.owner_name.ilike(term),
                PrintJob.job_id.ilike(term),
            )
        )

    return q


def _summary(jobs: list[PrintJob]) -> dict:
    total_pages = sum(j.printed_pages for j in jobs)
    waste_pages = sum(j.printed_pages for j in jobs if j.is_waste)
    return {
        "total_jobs": len(jobs),
        "total_pages": total_pages,
        "color_pages": sum(j.color_pages for j in jobs),
        "bw_pages": sum(j.bw_pages for j in jobs),
        "waste_pages": waste_pages,
        "waste_pct": round(waste_pages / total_pages * 100, 1) if total_pages else 0,
    }


def _job_out(j: PrintJob) -> dict:
    return {
        "id": j.id,
        "printer_id": j.printer_id,
        "job_id": j.job_id,
        "job_name": j.job_name,
        "status": j.status,
        "owner_name": j.owner_name,
        "recorded_at": j.recorded_at.isoformat() if j.recorded_at else None,
        "printed_pages": j.printed_pages,
        "color_pages": j.color_pages,
        "bw_pages": j.bw_pages,
        "paper_type": j.paper_type,
        "paper_size": j.paper_size,
        "copies": j.copies,
        "is_waste": j.is_waste,
        "computed_total_cost": float(j.computed_total_cost),
    }


@router.get("/jobs")
async def list_jobs(
    current_user: OwnerUser,
    db: Session = Depends(get_db),
    printer_ids: str | None = Query(None, description="Comma-separated printer IDs"),
    date_from: str | None = Query(None),
    date_to: str | None = Query(None),
    status: str = Query("all"),
    search: str | None = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    sort_by: str = Query("recorded_at"),
    sort_dir: str = Query("desc"),
):
    q = _build_query(db, current_user.id, printer_ids, date_from, date_to, status, search)
    if q is None:
        return {"data": {"jobs": [], "summary": _summary([]), "total": 0, "page": page, "per_page": per_page}, "message": "ok"}

    # Sorting
    sort_col = SORTABLE.get(sort_by, PrintJob.recorded_at)
    q = q.order_by(sort_col.desc() if sort_dir == "desc" else sort_col.asc())

    total = q.count()

    # Summary over ALL matching rows (not just current page)
    all_jobs = q.all()
    summary = _summary(all_jobs)

    # Paginate
    jobs = all_jobs[(page - 1) * per_page: page * per_page]

    return {
        "data": {
            "jobs": [_job_out(j) for j in jobs],
            "summary": summary,
            "total": total,
            "page": page,
            "per_page": per_page,
        },
        "message": "ok",
    }


@router.get("/jobs/export")
async def export_jobs_csv(
    current_user: OwnerUser,
    db: Session = Depends(get_db),
    printer_ids: str | None = Query(None),
    date_from: str | None = Query(None),
    date_to: str | None = Query(None),
    status: str = Query("all"),
    search: str | None = Query(None),
):
    q = _build_query(db, current_user.id, printer_ids, date_from, date_to, status, search)
    if q is None:
        jobs = []
    else:
        jobs = q.order_by(PrintJob.recorded_at.desc()).all()

    date_part = f"{date_from or 'all'}-to-{date_to or 'now'}"
    filename = f"printsight-report-{date_part}.csv"

    def generate():
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow([
            "Date", "Job ID", "Job Name", "Owner", "Status",
            "Total Pages", "Color Pages", "B&W Pages",
            "Paper Type", "Paper Size", "Copies", "Waste", "Printer ID"
        ])
        yield buf.getvalue()

        for j in jobs:
            buf = io.StringIO()
            writer = csv.writer(buf)
            writer.writerow([
                j.recorded_at.strftime("%Y-%m-%d %H:%M") if j.recorded_at else "",
                j.job_id,
                j.job_name or "",
                j.owner_name or "",
                j.status or "",
                j.printed_pages,
                j.color_pages,
                j.bw_pages,
                j.paper_type or "",
                j.paper_size or "",
                j.copies,
                "Yes" if j.is_waste else "No",
                j.printer_id,
            ])
            yield buf.getvalue()

    return StreamingResponse(
        generate(),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
