"""Analytics router — dashboard summary, cost trends, printer comparison."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Query
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

    q = db.query(PrintJob).filter(
        PrintJob.printer_id.in_(printer_ids),
        PrintJob.recorded_at >= start,
        PrintJob.recorded_at <= end,
    )
    if printer_id:
        q = q.filter(PrintJob.printer_id == printer_id)

    jobs = q.all()
    if not jobs:
        return {"data": _empty_summary(period), "message": "ok"}

    total_cost = sum(float(j.computed_total_cost) for j in jobs)
    paper_cost = sum(float(j.computed_paper_cost) for j in jobs)
    toner_cost = sum(float(j.computed_toner_cost) for j in jobs)
    total_pages = sum(j.printed_pages for j in jobs)
    waste_jobs = [j for j in jobs if j.is_waste]
    waste_cost = sum(float(j.computed_total_cost) for j in waste_jobs)
    waste_pages = sum(j.printed_pages for j in waste_jobs)
    color_pages = sum(j.color_pages for j in jobs)
    bw_pages = sum(j.bw_pages for j in jobs)

    return {
        "data": {
            "period": period,
            "total_cost": round(total_cost, 2),
            "paper_cost": round(paper_cost, 2),
            "toner_cost": round(toner_cost, 2),
            "total_pages": total_pages,
            "total_jobs": len(jobs),
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

    q = db.query(PrintJob).filter(
        PrintJob.printer_id.in_(printer_ids),
        PrintJob.recorded_at >= start,
        PrintJob.recorded_at <= end,
    )
    if printer_id:
        q = q.filter(PrintJob.printer_id == printer_id)

    jobs = q.all()
    by_bucket: dict[str, dict] = {}
    for j in jobs:
        if not j.recorded_at:
            continue
        bucket = _bucket_key(j.recorded_at, granularity)
        if bucket not in by_bucket:
            by_bucket[bucket] = {"date": bucket, "total_cost": 0.0, "paper_cost": 0.0, "toner_cost": 0.0, "pages": 0, "waste_cost": 0.0, "jobs": 0}
        by_bucket[bucket]["total_cost"] += float(j.computed_total_cost)
        by_bucket[bucket]["paper_cost"] += float(j.computed_paper_cost)
        by_bucket[bucket]["toner_cost"] += float(j.computed_toner_cost)
        by_bucket[bucket]["pages"] += j.printed_pages
        if j.is_waste:
            by_bucket[bucket]["waste_cost"] += float(j.computed_total_cost)
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
    printers = db.query(Printer).all()
    result = []
    for p in printers:
        jobs = db.query(PrintJob).filter(
            PrintJob.printer_id == p.id,
            PrintJob.recorded_at >= start,
            PrintJob.recorded_at <= end,
        ).all()
        total_cost = sum(float(j.computed_total_cost) for j in jobs)
        total_pages = sum(j.printed_pages for j in jobs)
        result.append({
            "printer_id": p.id,
            "printer_name": p.name,
            "total_cost": round(total_cost, 2),
            "total_pages": total_pages,
            "total_jobs": len(jobs),
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

    q = db.query(PrintJob).filter(
        PrintJob.printer_id.in_(printer_ids),
        PrintJob.recorded_at >= start,
        PrintJob.recorded_at <= end,
    )
    if printer_id:
        q = q.filter(PrintJob.printer_id == printer_id)

    jobs = q.all()
    paper = sum(float(j.computed_paper_cost) for j in jobs)
    toner = sum(float(j.computed_toner_cost) for j in jobs)
    waste = sum(float(j.computed_total_cost) for j in jobs if j.is_waste)

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

    q = db.query(PrintJob).filter(
        PrintJob.printer_id.in_(printer_ids),
        PrintJob.recorded_at >= start,
        PrintJob.recorded_at <= end,
    )
    if printer_id:
        q = q.filter(PrintJob.printer_id == printer_id)

    by_bucket: dict[str, dict] = {}
    for j in q.all():
        if not j.recorded_at:
            continue
        b = _bucket_key(j.recorded_at, granularity)
        slot = by_bucket.setdefault(b, {"bucket": b, "paper": 0.0})
        slot["paper"] += float(j.computed_paper_cost)
        for k, v in (j.computed_toner_cost_breakdown or {}).items():
            slot[k] = slot.get(k, 0.0) + float(v)

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

    q = db.query(PrintJob).filter(
        PrintJob.printer_id.in_(printer_ids),
        PrintJob.recorded_at >= start,
        PrintJob.recorded_at <= end,
    )
    if printer_id:
        q = q.filter(PrintJob.printer_id == printer_id)

    groups: dict[str, dict] = {}
    for j in q.all():
        key = j.paper_type or "(unknown)"
        slot = groups.setdefault(key, {"paper_type": key, "cost": 0.0, "pages": 0})
        slot["cost"] += float(j.computed_paper_cost)
        slot["pages"] += j.printed_pages

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
                "breakdown": j.computed_toner_cost_breakdown,
                "source": j.cost_computation_source,
                "is_waste": j.is_waste,
            }
            for j in jobs
        ],
        "message": "ok",
    }
