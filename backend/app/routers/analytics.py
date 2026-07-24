"""Analytics router — dashboard summary, cost trends, printer comparison."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import case, func
from sqlalchemy.orm import Session

from app.auth.deps import OwnerUser
from app.database import get_db
from app.models.printer import Printer
from app.models.upload import PrintJob

router = APIRouter(prefix="/analytics", tags=["analytics"])


def _resolve_range(
    period: Optional[str],
    start_date: Optional[datetime],
    end_date: Optional[datetime],
) -> tuple[datetime, datetime]:
    now = datetime.now(timezone.utc)
    if start_date and end_date:
        return start_date, end_date
    if period == "1d":
        return now - timedelta(days=1), now
    if period == "7d":
        return now - timedelta(days=7), now
    if period == "30d":
        return now - timedelta(days=30), now
    if period == "90d":
        return now - timedelta(days=90), now
    if period == "365d":
        return now - timedelta(days=365), now
    return now - timedelta(days=30), now


def _auto_granularity(start: datetime, end: datetime) -> str:
    span = (end - start).days
    if span <= 2:
        return "hour"
    if span <= 62:
        return "day"
    if span <= 400:
        return "week"
    return "month"


def _bucket_key(dt: datetime, granularity: str) -> str:
    if granularity == "hour":
        return dt.strftime("%Y-%m-%d %H:00")
    if granularity == "week":
        iso = dt.isocalendar()
        return f"{iso.year}-W{iso.week:02d}"
    if granularity == "month":
        return dt.strftime("%Y-%m")
    return dt.strftime("%Y-%m-%d")


def _empty_summary(period: Optional[str]) -> dict:
    return {
        "period": period,
        "total_cost": 0,
        "total_pages": 0,
        "total_jobs": 0,
        "paper_cost": 0,
        "toner_cost": 0,
        "waste_cost": 0,
        "waste_pages": 0,
        "waste_pct": 0,
        "color_pages": 0,
        "bw_pages": 0,
        "color_pct": 0,
        "cost_per_page": 0,
    }


@router.get("/summary")
async def summary(
    current_user: OwnerUser,
    db: Session = Depends(get_db),
    period: Optional[str] = Query(None),
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    printer_id: Optional[int] = Query(None),
):
    start, end = _resolve_range(period, start_date, end_date)
    printer_ids = [p.id for p in db.query(Printer.id).all()]
    if not printer_ids:
        return {"data": _empty_summary(period), "message": "ok"}

    row = (
        db.query(
            func.coalesce(func.sum(PrintJob.computed_total_cost), 0),
            func.coalesce(func.sum(PrintJob.computed_paper_cost), 0),
            func.coalesce(func.sum(PrintJob.computed_toner_cost), 0),
            func.coalesce(func.sum(PrintJob.printed_pages), 0),
            func.count(PrintJob.id),
            func.coalesce(func.sum(case((PrintJob.is_waste, PrintJob.computed_total_cost), else_=0)), 0),
            func.coalesce(func.sum(case((PrintJob.is_waste, PrintJob.printed_pages), else_=0)), 0),
            func.coalesce(func.sum(PrintJob.color_pages), 0),
            func.coalesce(func.sum(PrintJob.bw_pages), 0),
        )
        .filter(
            PrintJob.printer_id.in_(printer_ids),
            PrintJob.recorded_at >= start,
            PrintJob.recorded_at <= end,
        )
    )
    if printer_id:
        row = row.filter(PrintJob.printer_id == printer_id)
    (total_cost, paper_cost, toner_cost, total_pages, total_jobs,
     waste_cost, waste_pages, color_pages, bw_pages) = row.one()

    total_cost = float(total_cost); paper_cost = float(paper_cost)
    toner_cost = float(toner_cost); total_pages = int(total_pages)
    waste_cost = float(waste_cost); waste_pages = int(waste_pages)
    color_pages = int(color_pages); bw_pages = int(bw_pages)

    if total_jobs == 0:
        return {"data": _empty_summary(period), "message": "ok"}

    return {
        "data": {
            "period": period,
            "total_cost": round(total_cost, 2),
            "paper_cost": round(paper_cost, 2),
            "toner_cost": round(toner_cost, 2),
            "total_pages": total_pages,
            "total_jobs": total_jobs,
            "waste_cost": round(waste_cost, 2),
            "waste_pages": waste_pages,
            "waste_pct": round(waste_pages / total_pages * 100, 1) if total_pages else 0,
            "color_pages": color_pages,
            "bw_pages": bw_pages,
            "color_pct": round(color_pages / total_pages * 100, 1) if total_pages else 0,
            "cost_per_page": round(total_cost / total_pages, 4) if total_pages else 0,
        },
        "message": "ok",
    }


@router.get("/trends")
async def trends(
    current_user: OwnerUser,
    db: Session = Depends(get_db),
    period: Optional[str] = Query(None),
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    granularity: str = Query("auto"),
    printer_id: Optional[int] = Query(None),
):
    start, end = _resolve_range(period, start_date, end_date)
    if granularity == "auto":
        granularity = _auto_granularity(start, end)

    printer_ids = [p.id for p in db.query(Printer.id).all()]
    if not printer_ids:
        return {"data": [], "message": "ok"}

    rows = (
        db.query(
            PrintJob.recorded_at, PrintJob.computed_total_cost,
            PrintJob.computed_paper_cost, PrintJob.computed_toner_cost,
            PrintJob.printed_pages, PrintJob.is_waste,
        )
        .filter(
            PrintJob.printer_id.in_(printer_ids),
            PrintJob.recorded_at >= start, PrintJob.recorded_at <= end,
        )
    )
    if printer_id:
        rows = rows.filter(PrintJob.printer_id == printer_id)

    by_bucket: dict[str, dict] = {}
    for recorded_at, total, paper, toner, pages, is_waste in rows.all():
        if not recorded_at:
            continue
        bucket = _bucket_key(recorded_at, granularity)
        if bucket not in by_bucket:
            by_bucket[bucket] = {"date": bucket, "total_cost": 0.0, "paper_cost": 0.0, "toner_cost": 0.0, "pages": 0, "waste_cost": 0.0, "jobs": 0}
        by_bucket[bucket]["total_cost"] += float(total)
        by_bucket[bucket]["paper_cost"] += float(paper)
        by_bucket[bucket]["toner_cost"] += float(toner)
        by_bucket[bucket]["pages"] += pages
        if is_waste:
            by_bucket[bucket]["waste_cost"] += float(total)
        by_bucket[bucket]["jobs"] += 1

    trend_data = sorted(by_bucket.values(), key=lambda x: x["date"])
    for d in trend_data:
        d["total_cost"] = round(d["total_cost"], 2)
        d["paper_cost"] = round(d["paper_cost"], 2)
        d["toner_cost"] = round(d["toner_cost"], 2)
        d["waste_cost"] = round(d["waste_cost"], 2)

    return {"data": trend_data, "granularity": granularity, "message": "ok"}


@router.get("/printers-comparison")
async def printers_comparison(
    current_user: OwnerUser,
    db: Session = Depends(get_db),
    period: Optional[str] = Query(None),
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
):
    start, end = _resolve_range(period, start_date, end_date)
    rows = (
        db.query(
            Printer.id, Printer.name,
            func.coalesce(func.sum(PrintJob.computed_total_cost), 0),
            func.coalesce(func.sum(PrintJob.printed_pages), 0),
            func.count(PrintJob.id),
        )
        .outerjoin(
            PrintJob,
            (PrintJob.printer_id == Printer.id)
            & (PrintJob.recorded_at >= start)
            & (PrintJob.recorded_at <= end),
        )
        .group_by(Printer.id, Printer.name)
        .all()
    )
    result = []
    for pid, name, total_cost, total_pages, total_jobs in rows:
        total_cost = float(total_cost); total_pages = int(total_pages)
        result.append({
            "printer_id": pid, "printer_name": name,
            "total_cost": round(total_cost, 2), "total_pages": total_pages,
            "total_jobs": int(total_jobs),
            "cost_per_page": round(total_cost / total_pages, 4) if total_pages else 0,
        })
    return {"data": result, "message": "ok"}


@router.get("/cost-breakdown")
async def cost_breakdown(
    current_user: OwnerUser,
    db: Session = Depends(get_db),
    period: Optional[str] = Query(None),
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    printer_id: Optional[int] = Query(None),
):
    start, end = _resolve_range(period, start_date, end_date)
    printer_ids = [p.id for p in db.query(Printer.id).all()]
    if not printer_ids:
        return {"data": {}, "message": "ok"}

    row = (
        db.query(
            func.coalesce(func.sum(PrintJob.computed_paper_cost), 0),
            func.coalesce(func.sum(PrintJob.computed_toner_cost), 0),
            func.coalesce(func.sum(case((PrintJob.is_waste, PrintJob.computed_total_cost), else_=0)), 0),
        )
        .filter(
            PrintJob.printer_id.in_(printer_ids),
            PrintJob.recorded_at >= start,
            PrintJob.recorded_at <= end,
        )
    )
    if printer_id:
        row = row.filter(PrintJob.printer_id == printer_id)
    paper, toner, waste = row.one()
    paper = float(paper); toner = float(toner); waste = float(waste)

    return {
        "data": {
            "paper_cost": round(paper, 2),
            "toner_cost": round(toner, 2),
            "waste_cost": round(waste, 2),
            "total": round(paper + toner, 2),
        },
        "message": "ok",
    }


@router.get("/toner-breakdown")
async def toner_breakdown(
    current_user: OwnerUser,
    db: Session = Depends(get_db),
    period: Optional[str] = Query(None),
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    granularity: str = Query("auto"),
    printer_id: Optional[int] = Query(None),
):
    start, end = _resolve_range(period, start_date, end_date)
    if granularity == "auto":
        granularity = _auto_granularity(start, end)

    printer_ids = [p.id for p in db.query(Printer.id).all()]
    if not printer_ids:
        return {"data": [], "message": "ok"}

    _EST_COLS = [
        ("k", PrintJob.coverage_est_k), ("c", PrintJob.coverage_est_c),
        ("m", PrintJob.coverage_est_m), ("y", PrintJob.coverage_est_y),
        ("gld_1", PrintJob.coverage_est_gld_1), ("slv_1", PrintJob.coverage_est_slv_1),
        ("clr_1", PrintJob.coverage_est_clr_1), ("wht_1", PrintJob.coverage_est_wht_1),
        ("cr_1", PrintJob.coverage_est_cr_1), ("p_1", PrintJob.coverage_est_p_1),
        ("pa_1", PrintJob.coverage_est_pa_1), ("gld_6", PrintJob.coverage_est_gld_6),
        ("slv_6", PrintJob.coverage_est_slv_6), ("wht_6", PrintJob.coverage_est_wht_6),
        ("p_6", PrintJob.coverage_est_p_6),
    ]
    rows = (
        db.query(PrintJob.recorded_at, PrintJob.computed_paper_cost,
                 *[col for _, col in _EST_COLS])
        .filter(PrintJob.printer_id.in_(printer_ids),
                PrintJob.recorded_at >= start, PrintJob.recorded_at <= end)
    )
    if printer_id:
        rows = rows.filter(PrintJob.printer_id == printer_id)
    by_bucket: dict[str, dict] = {}
    for r in rows.all():
        if not r[0]:
            continue
        b = _bucket_key(r[0], granularity)
        slot = by_bucket.setdefault(b, {"bucket": b, "paper": 0.0})
        slot["paper"] += float(r[1] or 0)
        for i, (name, _) in enumerate(_EST_COLS):
            v = r[2 + i]
            if v:
                slot[name] = slot.get(name, 0.0) + float(v)

    return {
        "data": sorted(by_bucket.values(), key=lambda x: x["bucket"]),
        "granularity": granularity,
        "message": "ok",
    }


@router.get("/paper-breakdown")
async def paper_breakdown(
    current_user: OwnerUser,
    db: Session = Depends(get_db),
    period: Optional[str] = Query(None),
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    printer_id: Optional[int] = Query(None),
):
    start, end = _resolve_range(period, start_date, end_date)
    printer_ids = [p.id for p in db.query(Printer.id).all()]
    if not printer_ids:
        return {"data": [], "message": "ok"}

    rows = db.query(
        PrintJob.paper_type, PrintJob.computed_paper_cost, PrintJob.printed_pages
    ).filter(
        PrintJob.printer_id.in_(printer_ids),
        PrintJob.recorded_at >= start,
        PrintJob.recorded_at <= end,
    )
    if printer_id:
        rows = rows.filter(PrintJob.printer_id == printer_id)

    groups: dict[str, dict] = {}
    for paper_type, paper_cost, pages in rows.all():
        key = paper_type or "(unknown)"
        slot = groups.setdefault(key, {"paper_type": key, "cost": 0.0, "pages": 0})
        slot["cost"] += float(paper_cost)
        slot["pages"] += pages

    data = sorted(groups.values(), key=lambda x: x["cost"], reverse=True)
    for d in data:
        d["cost"] = round(d["cost"], 2)
    return {"data": data, "message": "ok"}


@router.get("/top-jobs")
async def top_jobs(
    current_user: OwnerUser,
    db: Session = Depends(get_db),
    period: Optional[str] = Query(None),
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    printer_id: Optional[int] = Query(None),
    limit: int = Query(20, ge=1, le=100),
    order: str = Query("cost", pattern="^(cost|pages|waste)$"),
):
    start, end = _resolve_range(period, start_date, end_date)
    printer_ids = [p.id for p in db.query(Printer.id).all()]
    if not printer_ids:
        return {"data": [], "message": "ok"}

    q = db.query(PrintJob).filter(
        PrintJob.printer_id.in_(printer_ids),
        PrintJob.recorded_at >= start,
        PrintJob.recorded_at <= end,
    )
    if printer_id:
        q = q.filter(PrintJob.printer_id == printer_id)
    if order == "waste":
        q = q.filter(PrintJob.is_waste.is_(True))

    sort_col = {
        "cost": PrintJob.computed_total_cost.desc(),
        "pages": PrintJob.printed_pages.desc(),
        "waste": PrintJob.computed_total_cost.desc(),
    }[order]
    jobs = q.order_by(sort_col).limit(limit).all()

    return {
        "data": [
            {
                "id": j.id,
                "job_id": j.job_id,
                "job_name": j.job_name,
                "recorded_at": j.recorded_at.isoformat() if j.recorded_at else None,
                "paper_type": j.paper_type,
                "printed_pages": j.printed_pages,
                "paper_cost": float(j.computed_paper_cost),
                "toner_cost": float(j.computed_toner_cost),
                "total_cost": float(j.computed_total_cost),
                "source": j.cost_computation_source,
                "is_waste": j.is_waste,
            }
            for j in jobs
        ],
        "message": "ok",
    }
