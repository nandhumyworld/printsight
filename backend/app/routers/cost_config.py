"""Cost configuration router — paper types and their prices."""

from __future__ import annotations

from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.auth.deps import CurrentUser, OwnerUser
from app.database import get_db
from app.models.paper import Paper, PrinterPaper

router = APIRouter(prefix="/cost-config", tags=["cost-config"])


class PaperCreate(BaseModel):
    name: str
    display_name: str | None = None
    length_mm: float | None = None
    width_mm: float | None = None
    length_tolerance_mm: float = 2.0
    width_tolerance_mm: float = 2.0
    gsm_min: int | None = None
    gsm_max: int | None = None
    counter_multiplier: float = 1.0
    price_per_sheet: float
    currency: str = "INR"
    printer_ids: list[int] = []


class PaperUpdate(BaseModel):
    display_name: str | None = None
    price_per_sheet: float | None = None
    currency: str | None = None
    counter_multiplier: float | None = None
    gsm_min: int | None = None
    gsm_max: int | None = None
    length_tolerance_mm: float | None = None
    width_tolerance_mm: float | None = None


def _paper_out(p: Paper) -> dict:
    return {
        "id": p.id,
        "name": p.name,
        "display_name": p.display_name,
        "length_mm": float(p.length_mm) if p.length_mm else None,
        "width_mm": float(p.width_mm) if p.width_mm else None,
        "length_tolerance_mm": float(p.length_tolerance_mm),
        "width_tolerance_mm": float(p.width_tolerance_mm),
        "gsm_min": p.gsm_min,
        "gsm_max": p.gsm_max,
        "counter_multiplier": float(p.counter_multiplier),
        "price_per_sheet": float(p.price_per_sheet),
        "currency": p.currency,
        "created_at": p.created_at.isoformat(),
    }


@router.get("/papers")
async def list_papers(current_user: CurrentUser, db: Session = Depends(get_db)):
    papers = db.query(Paper).filter(Paper.owner_id == current_user.id).all()
    return {"data": [_paper_out(p) for p in papers], "message": "ok"}


@router.post("/papers", status_code=201)
async def create_paper(body: PaperCreate, current_user: OwnerUser, db: Session = Depends(get_db)):
    existing = db.query(Paper).filter(Paper.owner_id == current_user.id, Paper.name == body.name).first()
    if existing:
        raise HTTPException(status_code=409, detail=f"Paper '{body.name}' already exists")
    p = Paper(
        owner_id=current_user.id,
        name=body.name,
        display_name=body.display_name,
        length_mm=Decimal(str(body.length_mm)) if body.length_mm else None,
        width_mm=Decimal(str(body.width_mm)) if body.width_mm else None,
        length_tolerance_mm=Decimal(str(body.length_tolerance_mm)),
        width_tolerance_mm=Decimal(str(body.width_tolerance_mm)),
        gsm_min=body.gsm_min,
        gsm_max=body.gsm_max,
        counter_multiplier=Decimal(str(body.counter_multiplier)),
        price_per_sheet=Decimal(str(body.price_per_sheet)),
        currency=body.currency,
    )
    db.add(p)
    db.flush()
    for pid in body.printer_ids:
        db.add(PrinterPaper(printer_id=pid, paper_id=p.id))
    db.commit()
    db.refresh(p)
    return {"data": _paper_out(p), "message": "Paper created"}


@router.put("/papers/{paper_id}")
async def update_paper(paper_id: int, body: PaperUpdate, current_user: OwnerUser, db: Session = Depends(get_db)):
    p = db.query(Paper).filter(Paper.id == paper_id, Paper.owner_id == current_user.id).first()
    if not p:
        raise HTTPException(status_code=404, detail="Paper not found")
    if body.display_name is not None:
        p.display_name = body.display_name
    if body.price_per_sheet is not None:
        p.price_per_sheet = Decimal(str(body.price_per_sheet))
    if body.currency is not None:
        p.currency = body.currency
    if body.counter_multiplier is not None:
        p.counter_multiplier = Decimal(str(body.counter_multiplier))
    if body.gsm_min is not None:
        p.gsm_min = body.gsm_min
    if body.gsm_max is not None:
        p.gsm_max = body.gsm_max
    if body.length_tolerance_mm is not None:
        p.length_tolerance_mm = Decimal(str(body.length_tolerance_mm))
    if body.width_tolerance_mm is not None:
        p.width_tolerance_mm = Decimal(str(body.width_tolerance_mm))
    db.commit()
    db.refresh(p)
    return {"data": _paper_out(p), "message": "Paper updated"}


@router.delete("/papers/{paper_id}", status_code=204)
async def delete_paper(paper_id: int, current_user: OwnerUser, db: Session = Depends(get_db)):
    p = db.query(Paper).filter(Paper.id == paper_id, Paper.owner_id == current_user.id).first()
    if not p:
        raise HTTPException(status_code=404, detail="Paper not found")
    db.delete(p)
    db.commit()
