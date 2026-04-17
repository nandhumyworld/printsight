"""Analytics router — dashboard summary, cost trends, printer comparison."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.auth.deps import OwnerUser
from app.database import get_db
from app.models.printer import Printer
from app.models.upload import PrintJob

router = APIRouter(prefix="/analytics", tags=["analytics"])


def _date_range(period: str) -> tuple[datetime, datetime]:
    now = datetime.now(timezone.utc)
    if period == "7d":
        start = now - timedelta(days=7)
    elif period == "30d":
        start = now - timedelta(days=30)
    elif period == "90d":
        start = now - timedelta(days=90)
    else:
        start = now - timedelta(days=30)
    return start, now


@router.get("/summary")
async def summary(
    current_user: OwnerUser,
    db: Session = Depends(get_db),
    period: str = Query("30d", pattern="^(7d|30d|90d)$"),
    printer_id: int | None = Query(None),
):
    start, end = _date_range(period)
    printer_ids = [p.id for p in db.query(Printer.id).filter(Printer.owner_id == current_user.id).all()]
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
    period: str = Query("30d", pattern="^(7d|30d|90d)$"),
    printer_id: int | None = Query(None),
):
    start, end = _date_range(period)
    printer_ids = [p.id for p in db.query(Printer.id).filter(Printer.owner_id == current_user.id).all()]
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
    by_day: dict[str, dict] = {}
    for j in jobs:
        if not j.recorded_at:
            continue
        day = j.recorded_at.strftime("%Y-%m-%d")
        if day not in by_day:
            by_day[day] = {"date": day, "total_cost": 0.0, "pages": 0, "waste_cost": 0.0, "jobs": 0}
        by_day[day]["total_cost"] += float(j.computed_total_cost)
        by_day[day]["pages"] += j.printed_pages
        if j.is_waste:
            by_day[day]["waste_cost"] += float(j.computed_total_cost)
        by_day[day]["jobs"] += 1

    trend_data = sorted(by_day.values(), key=lambda x: x["date"])
    for d in trend_data:
        d["total_cost"] = round(d["total_cost"], 2)
        d["waste_cost"] = round(d["waste_cost"], 2)

    return {"data": trend_data, "message": "ok"}


@router.get("/printers-comparison")
async def printers_comparison(
    current_user: OwnerUser,
    db: Session = Depends(get_db),
    period: str = Query("30d", pattern="^(7d|30d|90d)$"),
):
    start, end = _date_range(period)
    printers = db.query(Printer).filter(Printer.owner_id == current_user.id).all()
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
    period: str = Query("30d", pattern="^(7d|30d|90d)$"),
    printer_id: int | None = Query(None),
):
    start, end = _date_range(period)
    printer_ids = [p.id for p in db.query(Printer.id).filter(Printer.owner_id == current_user.id).all()]
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


def _empty_summary(period: str) -> dict:
    return {
        "period": period,
        "total_cost": 0,
        "total_pages": 0,
        "total_jobs": 0,
        "waste_cost": 0,
        "waste_pages": 0,
        "waste_pct": 0,
        "color_pages": 0,
        "bw_pages": 0,
        "color_pct": 0,
        "cost_per_page": 0,
    }
