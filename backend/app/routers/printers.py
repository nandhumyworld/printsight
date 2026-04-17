"""Printers router — CRUD for printers and toner configs."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.auth.deps import CurrentUser, OwnerUser
from app.database import get_db
from app.models.printer import Printer
from app.models.toner import Toner, TonerType

router = APIRouter(prefix="/printers", tags=["printers"])


# ---- Pydantic schemas (inline for simplicity) ----
class PrinterCreate(BaseModel):
    name: str
    model: str | None = None
    type: str | None = None
    serial_number: str | None = None
    location: str | None = None
    column_mapping: dict[str, str] = {}


class PrinterUpdate(BaseModel):
    name: str | None = None
    model: str | None = None
    type: str | None = None
    serial_number: str | None = None
    location: str | None = None
    is_active: bool | None = None
    column_mapping: dict[str, str] | None = None


class TonerCreate(BaseModel):
    toner_color: str
    toner_type: str = "standard"
    price_per_unit: float
    rated_yield_pages: int
    currency: str = "INR"


def _printer_out(p: Printer) -> dict[str, Any]:
    return {
        "id": p.id,
        "owner_id": p.owner_id,
        "name": p.name,
        "model": p.model,
        "type": p.type,
        "serial_number": p.serial_number,
        "location": p.location,
        "column_mapping": p.column_mapping,
        "is_active": p.is_active,
        "created_at": p.created_at.isoformat(),
        "updated_at": p.updated_at.isoformat(),
    }


def _get_printer_or_404(db: Session, printer_id: int, owner_id: int) -> Printer:
    p = db.query(Printer).filter(Printer.id == printer_id, Printer.owner_id == owner_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="Printer not found")
    return p


@router.get("")
async def list_printers(current_user: CurrentUser, db: Session = Depends(get_db)):
    printers = db.query(Printer).filter(Printer.owner_id == current_user.id).all()
    return {"data": [_printer_out(p) for p in printers], "message": "ok"}


@router.post("", status_code=201)
async def create_printer(body: PrinterCreate, current_user: OwnerUser, db: Session = Depends(get_db)):
    p = Printer(owner_id=current_user.id, **body.model_dump())
    db.add(p)
    db.commit()
    db.refresh(p)
    return {"data": _printer_out(p), "message": "Printer created"}


@router.get("/{printer_id}")
async def get_printer(printer_id: int, current_user: CurrentUser, db: Session = Depends(get_db)):
    p = _get_printer_or_404(db, printer_id, current_user.id)
    return {"data": _printer_out(p), "message": "ok"}


@router.put("/{printer_id}")
async def update_printer(printer_id: int, body: PrinterUpdate, current_user: OwnerUser, db: Session = Depends(get_db)):
    p = _get_printer_or_404(db, printer_id, current_user.id)
    for field, val in body.model_dump(exclude_none=True).items():
        setattr(p, field, val)
    db.commit()
    db.refresh(p)
    return {"data": _printer_out(p), "message": "Printer updated"}


@router.delete("/{printer_id}", status_code=204)
async def delete_printer(printer_id: int, current_user: OwnerUser, db: Session = Depends(get_db)):
    p = _get_printer_or_404(db, printer_id, current_user.id)
    db.delete(p)
    db.commit()


# ---- Toner sub-resource ----
@router.get("/{printer_id}/toners")
async def list_toners(printer_id: int, current_user: CurrentUser, db: Session = Depends(get_db)):
    _get_printer_or_404(db, printer_id, current_user.id)
    toners = db.query(Toner).filter(Toner.printer_id == printer_id).all()
    return {"data": [_toner_out(t) for t in toners], "message": "ok"}


@router.post("/{printer_id}/toners", status_code=201)
async def create_toner(printer_id: int, body: TonerCreate, current_user: OwnerUser, db: Session = Depends(get_db)):
    _get_printer_or_404(db, printer_id, current_user.id)
    t = Toner(
        printer_id=printer_id,
        toner_color=body.toner_color,
        toner_type=TonerType(body.toner_type),
        price_per_unit=body.price_per_unit,
        rated_yield_pages=body.rated_yield_pages,
        currency=body.currency,
    )
    db.add(t)
    db.commit()
    db.refresh(t)
    return {"data": _toner_out(t), "message": "Toner created"}


@router.put("/{printer_id}/toners/{toner_id}")
async def update_toner(printer_id: int, toner_id: int, body: TonerCreate, current_user: OwnerUser, db: Session = Depends(get_db)):
    _get_printer_or_404(db, printer_id, current_user.id)
    t = db.query(Toner).filter(Toner.id == toner_id, Toner.printer_id == printer_id).first()
    if not t:
        raise HTTPException(status_code=404, detail="Toner not found")
    t.toner_color = body.toner_color
    t.toner_type = TonerType(body.toner_type)
    t.price_per_unit = body.price_per_unit
    t.rated_yield_pages = body.rated_yield_pages
    t.currency = body.currency
    db.commit()
    db.refresh(t)
    return {"data": _toner_out(t), "message": "Toner updated"}


@router.delete("/{printer_id}/toners/{toner_id}", status_code=204)
async def delete_toner(printer_id: int, toner_id: int, current_user: OwnerUser, db: Session = Depends(get_db)):
    _get_printer_or_404(db, printer_id, current_user.id)
    t = db.query(Toner).filter(Toner.id == toner_id, Toner.printer_id == printer_id).first()
    if not t:
        raise HTTPException(status_code=404, detail="Toner not found")
    db.delete(t)
    db.commit()


def _toner_out(t: Toner) -> dict[str, Any]:
    return {
        "id": t.id,
        "printer_id": t.printer_id,
        "toner_color": t.toner_color,
        "toner_type": t.toner_type.value,
        "price_per_unit": float(t.price_per_unit),
        "rated_yield_pages": t.rated_yield_pages,
        "currency": t.currency,
        "created_at": t.created_at.isoformat(),
    }
