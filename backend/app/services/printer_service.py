"""Printer lifecycle service — archive, restore, delete, purge."""
from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.printer import Printer
from app.models.upload import UploadBatch


def archive_printer(db: Session, printer: Printer) -> Printer:
    printer.is_active = False
    db.commit()
    db.refresh(printer)
    return printer


def restore_printer(db: Session, printer: Printer) -> Printer:
    printer.is_active = True
    db.commit()
    db.refresh(printer)
    return printer


def hard_delete_printer(db: Session, printer: Printer) -> None:
    """Delete printer if it has no uploaded jobs; raise 409 otherwise."""
    batch_count = db.query(UploadBatch).filter(UploadBatch.printer_id == printer.id).count()
    if batch_count > 0:
        raise HTTPException(
            status_code=409,
            detail=f"Cannot delete: printer has {batch_count} upload batch(es). Use purge to force-delete.",
        )
    db.delete(printer)
    db.commit()


def purge_printer(db: Session, printer: Printer, confirm_name: str) -> None:
    """Cascade-delete everything; caller must pass printer name as confirmation."""
    if confirm_name != printer.name:
        raise HTTPException(status_code=400, detail="Confirmation name does not match printer name")
    db.delete(printer)
    db.commit()
