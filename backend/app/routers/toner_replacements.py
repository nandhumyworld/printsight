"""Toner replacement logs router."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.auth.deps import CurrentUser, OwnerUser
from app.database import get_db
from app.models.printer import Printer
from app.models.toner import Toner, TonerReplacementLog

router = APIRouter(prefix="/toner-replacements", tags=["toner-replacements"])


class ReplacementCreate(BaseModel):
    printer_id: int
    toner_id: int
    counter_reading_at_replacement: int
    replaced_at: str  # ISO string
    cartridge_price_per_unit: float
    cartridge_rated_yield_pages: int
    cartridge_currency: str = "INR"
    notes: str | None = None


def _log_out(log: TonerReplacementLog) -> dict:
    toner = log.toner
    return {
        "id": log.id,
        "printer_id": log.printer_id,
        "toner_id": log.toner_id,
        "toner_color": toner.toner_color if toner else None,
        "toner_type": toner.toner_type.value if toner else None,
        "replaced_by_user_id": log.replaced_by_user_id,
        "counter_reading_at_replacement": log.counter_reading_at_replacement,
        "replaced_at": log.replaced_at.isoformat(),
        "cartridge_price_per_unit": float(log.cartridge_price_per_unit),
        "cartridge_rated_yield_pages": log.cartridge_rated_yield_pages,
        "cartridge_currency": log.cartridge_currency,
        "actual_yield_pages": log.actual_yield_pages,
        "yield_efficiency_pct": float(log.yield_efficiency_pct) if log.yield_efficiency_pct else None,
        "notes": log.notes,
        "created_at": log.created_at.isoformat(),
    }


@router.get("")
async def list_replacements(
    current_user: CurrentUser,
    printer_id: int | None = None,
    db: Session = Depends(get_db),
):
    # Get printer IDs owned by user
    from app.models.printer import Printer
    owner_printer_ids = [p.id for p in db.query(Printer.id).filter(Printer.owner_id == current_user.id).all()]

    from sqlalchemy.orm import joinedload
    q = db.query(TonerReplacementLog).options(joinedload(TonerReplacementLog.toner)).filter(TonerReplacementLog.printer_id.in_(owner_printer_ids))
    if printer_id:
        q = q.filter(TonerReplacementLog.printer_id == printer_id)
    logs = q.order_by(TonerReplacementLog.replaced_at.desc()).limit(100).all()
    return {"data": [_log_out(l) for l in logs], "message": "ok"}


@router.post("", status_code=201)
async def create_replacement(
    body: ReplacementCreate,
    current_user: CurrentUser,
    db: Session = Depends(get_db),
):
    printer = db.query(Printer).filter(Printer.id == body.printer_id, Printer.owner_id == current_user.id).first()
    if not printer:
        raise HTTPException(status_code=404, detail="Printer not found")

    toner = db.query(Toner).filter(Toner.id == body.toner_id, Toner.printer_id == body.printer_id).first()
    if not toner:
        raise HTTPException(status_code=404, detail="Toner not found")

    try:
        replaced_at = datetime.fromisoformat(body.replaced_at.replace("Z", "+00:00"))
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid replaced_at format")

    from decimal import Decimal

    # Compute actual yield from previous replacement
    prev = db.query(TonerReplacementLog).filter(
        TonerReplacementLog.toner_id == body.toner_id
    ).order_by(TonerReplacementLog.replaced_at.desc()).first()

    actual_yield = None
    efficiency_pct = None
    if prev:
        actual_yield = body.counter_reading_at_replacement - prev.counter_reading_at_replacement
        if actual_yield > 0 and body.cartridge_rated_yield_pages > 0:
            efficiency_pct = Decimal(str(round(actual_yield / body.cartridge_rated_yield_pages * 100, 2)))

    log = TonerReplacementLog(
        printer_id=body.printer_id,
        toner_id=body.toner_id,
        replaced_by_user_id=current_user.id,
        counter_reading_at_replacement=body.counter_reading_at_replacement,
        replaced_at=replaced_at,
        cartridge_price_per_unit=Decimal(str(body.cartridge_price_per_unit)),
        cartridge_rated_yield_pages=body.cartridge_rated_yield_pages,
        cartridge_currency=body.cartridge_currency,
        actual_yield_pages=actual_yield,
        yield_efficiency_pct=efficiency_pct,
        notes=body.notes,
    )
    db.add(log)
    db.commit()
    db.refresh(log)
    return {"data": _log_out(log), "message": "Replacement logged"}


@router.get("/yield-summary")
async def yield_summary(
    current_user: OwnerUser,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Per-toner yield efficiency summary for the toner yield report page."""
    owner_printer_ids = [
        p.id
        for p in db.query(Printer.id).filter(Printer.owner_id == current_user.id).all()
    ]

    logs = (
        db.query(TonerReplacementLog)
        .filter(TonerReplacementLog.printer_id.in_(owner_printer_ids))
        .order_by(TonerReplacementLog.replaced_at.desc())
        .all()
    )

    # Group by toner_id
    toner_map: dict[int, dict[str, Any]] = {}
    for log in logs:
        tid = log.toner_id
        if tid not in toner_map:
            toner = db.get(Toner, tid)
            printer = db.get(Printer, log.printer_id)
            toner_map[tid] = {
                "toner_id": tid,
                "toner_color": toner.toner_color if toner else "Unknown",
                "toner_type": toner.toner_type.value if toner else "standard",
                "rated_yield_pages": toner.rated_yield_pages if toner else None,
                "price_per_unit": float(toner.price_per_unit) if toner else None,
                "printer_name": printer.name if printer else f"Printer #{log.printer_id}",
                "printer_id": log.printer_id,
                "replacements": [],
                "avg_efficiency_pct": None,
                "avg_actual_yield": None,
            }
        if log.actual_yield_pages is not None:
            toner_map[tid]["replacements"].append({
                "id": log.id,
                "replaced_at": log.replaced_at.isoformat(),
                "counter_reading": log.counter_reading_at_replacement,
                "actual_yield_pages": log.actual_yield_pages,
                "yield_efficiency_pct": float(log.yield_efficiency_pct) if log.yield_efficiency_pct else None,
                "notes": log.notes,
            })

    # Compute averages
    for toner_data in toner_map.values():
        reps = toner_data["replacements"]
        if reps:
            efficiencies = [r["yield_efficiency_pct"] for r in reps if r["yield_efficiency_pct"] is not None]
            yields = [r["actual_yield_pages"] for r in reps if r["actual_yield_pages"] is not None]
            toner_data["avg_efficiency_pct"] = round(sum(efficiencies) / len(efficiencies), 1) if efficiencies else None
            toner_data["avg_actual_yield"] = round(sum(yields) / len(yields)) if yields else None
            toner_data["total_replacements"] = len(reps)
            toner_data["last_replaced_at"] = reps[0]["replaced_at"] if reps else None
        else:
            toner_data["total_replacements"] = 0
            toner_data["last_replaced_at"] = None

    return {"data": list(toner_map.values()), "message": "ok"}


@router.delete("/{log_id}", status_code=204)
async def delete_replacement(log_id: int, current_user: CurrentUser, db: Session = Depends(get_db)):
    log = db.query(TonerReplacementLog).filter(TonerReplacementLog.id == log_id).first()
    if not log:
        raise HTTPException(status_code=404, detail="Log not found")
    # Verify ownership via printer
    printer = db.query(Printer).filter(Printer.id == log.printer_id, Printer.owner_id == current_user.id).first()
    if not printer:
        raise HTTPException(status_code=403, detail="Forbidden")
    db.delete(log)
    db.commit()
