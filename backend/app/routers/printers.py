"""Printers router — CRUD for printers and toner configs."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.auth.deps import CurrentUser, OwnerUser
from app.database import get_db
from app.models.paper import Paper, PrinterPaper
from app.models.printer import Printer
from app.models.toner import Toner, TonerType
from app.services.printer_image_service import delete_printer_image, save_printer_image
from app.services.printer_service import (
    archive_printer,
    hard_delete_printer,
    purge_printer,
    restore_printer,
)

router = APIRouter(prefix="/printers", tags=["printers"])


# ---- Pydantic schemas ----

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
    image_url: str | None = None


class TonerCreate(BaseModel):
    toner_color: str
    toner_type: str = "standard"
    price_per_unit: float
    rated_yield_pages: int
    currency: str = "INR"


class PurgeBody(BaseModel):
    confirm_name: str


# ---- Helpers ----

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
        "image_url": p.image_url,
        "is_active": p.is_active,
        "created_at": p.created_at.isoformat(),
        "updated_at": p.updated_at.isoformat(),
    }


def _get_printer_or_404(db: Session, printer_id: int, owner_id: int) -> Printer:
    p = db.query(Printer).filter(Printer.id == printer_id, Printer.owner_id == owner_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="Printer not found")
    return p


# ---- Printer CRUD ----

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
    hard_delete_printer(db, p)


@router.post("/{printer_id}/archive")
async def archive(printer_id: int, current_user: OwnerUser, db: Session = Depends(get_db)):
    p = _get_printer_or_404(db, printer_id, current_user.id)
    return {"data": _printer_out(archive_printer(db, p)), "message": "Printer archived"}


@router.post("/{printer_id}/restore")
async def restore(printer_id: int, current_user: OwnerUser, db: Session = Depends(get_db)):
    p = _get_printer_or_404(db, printer_id, current_user.id)
    return {"data": _printer_out(restore_printer(db, p)), "message": "Printer restored"}


@router.post("/{printer_id}/purge", status_code=204)
async def purge(printer_id: int, body: PurgeBody, current_user: OwnerUser, db: Session = Depends(get_db)):
    p = _get_printer_or_404(db, printer_id, current_user.id)
    purge_printer(db, p, body.confirm_name)


# ---- Image sub-resource ----

@router.post("/{printer_id}/image")
async def upload_image(
    printer_id: int,
    file: UploadFile = File(...),
    current_user: OwnerUser = Depends(),
    db: Session = Depends(get_db),
):
    p = _get_printer_or_404(db, printer_id, current_user.id)
    if p.image_url:
        delete_printer_image(p.image_url)
    url = await save_printer_image(printer_id, file)
    p.image_url = url
    db.commit()
    db.refresh(p)
    return {"data": _printer_out(p), "message": "Image uploaded"}


@router.delete("/{printer_id}/image", status_code=204)
async def delete_image(printer_id: int, current_user: OwnerUser, db: Session = Depends(get_db)):
    p = _get_printer_or_404(db, printer_id, current_user.id)
    if p.image_url:
        delete_printer_image(p.image_url)
        p.image_url = None
        db.commit()


# ---- Printer-Paper link/unlink ----

@router.get("/{printer_id}/papers")
async def list_linked_papers(printer_id: int, current_user: CurrentUser, db: Session = Depends(get_db)):
    _get_printer_or_404(db, printer_id, current_user.id)
    links = db.query(PrinterPaper).filter(PrinterPaper.printer_id == printer_id).all()
    paper_ids = [lnk.paper_id for lnk in links]
    papers = db.query(Paper).filter(Paper.id.in_(paper_ids)).all() if paper_ids else []
    return {"data": [_paper_mini(p) for p in papers], "message": "ok"}


@router.post("/{printer_id}/papers/{paper_id}", status_code=201)
async def link_paper(printer_id: int, paper_id: int, current_user: OwnerUser, db: Session = Depends(get_db)):
    _get_printer_or_404(db, printer_id, current_user.id)
    paper = db.query(Paper).filter(Paper.id == paper_id, Paper.owner_id == current_user.id).first()
    if not paper:
        raise HTTPException(status_code=404, detail="Paper not found")
    existing = db.query(PrinterPaper).filter(
        PrinterPaper.printer_id == printer_id, PrinterPaper.paper_id == paper_id
    ).first()
    if existing:
        raise HTTPException(status_code=409, detail="Already linked")
    db.add(PrinterPaper(printer_id=printer_id, paper_id=paper_id))
    db.commit()
    return {"data": None, "message": "Paper linked"}


@router.delete("/{printer_id}/papers/{paper_id}", status_code=204)
async def unlink_paper(printer_id: int, paper_id: int, current_user: OwnerUser, db: Session = Depends(get_db)):
    _get_printer_or_404(db, printer_id, current_user.id)
    link = db.query(PrinterPaper).filter(
        PrinterPaper.printer_id == printer_id, PrinterPaper.paper_id == paper_id
    ).first()
    if not link:
        raise HTTPException(status_code=404, detail="Link not found")
    db.delete(link)
    db.commit()


def _paper_mini(p: Paper) -> dict:
    return {"id": p.id, "name": p.name, "display_name": p.display_name}


# ---- Column mapping export / import ----

@router.get("/{printer_id}/mapping/export")
async def export_mapping(printer_id: int, current_user: CurrentUser, db: Session = Depends(get_db)):
    from fastapi.responses import JSONResponse
    p = _get_printer_or_404(db, printer_id, current_user.id)
    return JSONResponse(
        content=p.column_mapping,
        headers={"Content-Disposition": f'attachment; filename="mapping_{printer_id}.json"'},
    )


@router.post("/{printer_id}/mapping/import/preview")
async def preview_mapping_import(
    printer_id: int,
    file: UploadFile = File(...),
    current_user: OwnerUser = Depends(),
    db: Session = Depends(get_db),
):
    import json
    p = _get_printer_or_404(db, printer_id, current_user.id)
    contents = await file.read()
    try:
        incoming: dict[str, str] = json.loads(contents)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON")
    from app.services.column_mapping_service import compute_diff
    diff = compute_diff(p.column_mapping or {}, incoming)
    return {"data": {"diff": diff, "incoming": incoming}, "message": "ok"}


@router.post("/{printer_id}/mapping/import/apply")
async def apply_mapping_import(
    printer_id: int,
    file: UploadFile = File(...),
    current_user: OwnerUser = Depends(),
    db: Session = Depends(get_db),
):
    import json
    p = _get_printer_or_404(db, printer_id, current_user.id)
    contents = await file.read()
    try:
        incoming: dict[str, str] = json.loads(contents)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON")
    p.column_mapping = incoming
    db.commit()
    db.refresh(p)
    return {"data": _printer_out(p), "message": "Mapping applied"}


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
