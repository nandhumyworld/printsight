"""Admin router — owner-only user management and system stats."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.auth.deps import OwnerUser
from app.database import get_db
from app.models.printer import Printer
from app.models.toner import TonerReplacementLog
from app.models.upload import PrintJob, UploadBatch
from app.models.user import User, UserRole

router = APIRouter(prefix="/admin", tags=["admin"])


class UserCreate(BaseModel):
    email: str
    full_name: str
    password: str
    role: str = "owner"


class UserUpdate(BaseModel):
    role: str | None = None
    is_active: bool | None = None
    full_name: str | None = None


def _user_out(u: User) -> dict[str, Any]:
    return {
        "id": u.id,
        "email": u.email,
        "full_name": u.full_name,
        "role": u.role.value,
        "is_active": u.is_active,
        "created_at": u.created_at.isoformat(),
        "updated_at": u.updated_at.isoformat(),
    }


@router.get("/stats")
async def get_admin_stats(current_user: OwnerUser, db: Session = Depends(get_db)):
    """System-wide stats for admin overview."""
    total_users = db.query(func.count(User.id)).scalar() or 0
    active_users = db.query(func.count(User.id)).filter(User.is_active == True).scalar() or 0  # noqa: E712
    owner_count = db.query(func.count(User.id)).filter(User.role == UserRole.owner).scalar() or 0
    print_person_count = db.query(func.count(User.id)).filter(User.role == UserRole.print_person).scalar() or 0

    total_printers = db.query(func.count(Printer.id)).scalar() or 0
    active_printers = db.query(func.count(Printer.id)).filter(Printer.is_active == True).scalar() or 0  # noqa: E712

    total_jobs = db.query(func.count(PrintJob.id)).scalar() or 0
    total_uploads = db.query(func.count(UploadBatch.id)).scalar() or 0
    total_replacements = db.query(func.count(TonerReplacementLog.id)).scalar() or 0

    return {
        "data": {
            "users": {
                "total": total_users,
                "active": active_users,
                "inactive": total_users - active_users,
                "owners": owner_count,
                "print_persons": print_person_count,
            },
            "printers": {
                "total": total_printers,
                "active": active_printers,
                "inactive": total_printers - active_printers,
            },
            "activity": {
                "total_jobs": total_jobs,
                "total_uploads": total_uploads,
                "total_toner_replacements": total_replacements,
            },
        },
        "message": "ok",
    }


@router.post("/users", status_code=201)
async def create_user(
    body: UserCreate,
    current_user: OwnerUser,
    db: Session = Depends(get_db),
):
    """Admin-create a user with any role and a known password."""
    import bcrypt

    if db.query(User).filter(User.email == body.email).first():
        raise HTTPException(status_code=409, detail="Email already registered")

    try:
        role = UserRole(body.role)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid role: {body.role}")

    if len(body.password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters")

    hashed = bcrypt.hashpw(body.password.encode(), bcrypt.gensalt()).decode()
    u = User(
        email=body.email,
        full_name=body.full_name,
        hashed_password=hashed,
        role=role,
        is_active=True,
    )
    db.add(u)
    db.commit()
    db.refresh(u)
    d = _user_out(u)
    d["printer_count"] = 0
    return {"data": d, "message": "User created"}


@router.get("/users")
async def list_users(
    current_user: OwnerUser,
    search: str | None = None,
    role: str | None = None,
    is_active: bool | None = None,
    db: Session = Depends(get_db),
):
    """List all users with optional filters."""
    q = db.query(User)
    if search:
        q = q.filter(
            (User.email.ilike(f"%{search}%")) | (User.full_name.ilike(f"%{search}%"))
        )
    if role:
        try:
            q = q.filter(User.role == UserRole(role))
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid role: {role}")
    if is_active is not None:
        q = q.filter(User.is_active == is_active)

    users = q.order_by(User.created_at.desc()).all()

    # Attach printer count per user
    printer_counts: dict[int, int] = {}
    for u in users:
        cnt = db.query(func.count(Printer.id)).filter(Printer.owner_id == u.id).scalar() or 0
        printer_counts[u.id] = cnt

    result = []
    for u in users:
        d = _user_out(u)
        d["printer_count"] = printer_counts.get(u.id, 0)
        result.append(d)

    return {"data": result, "message": "ok"}


@router.get("/users/{user_id}")
async def get_user(user_id: int, current_user: OwnerUser, db: Session = Depends(get_db)):
    u = db.get(User, user_id)
    if not u:
        raise HTTPException(status_code=404, detail="User not found")
    d = _user_out(u)
    d["printer_count"] = db.query(func.count(Printer.id)).filter(Printer.owner_id == u.id).scalar() or 0
    d["job_count"] = (
        db.query(func.count(PrintJob.id))
        .join(UploadBatch, PrintJob.upload_batch_id == UploadBatch.id)
        .join(Printer, UploadBatch.printer_id == Printer.id)
        .filter(Printer.owner_id == u.id)
        .scalar() or 0
    )
    return {"data": d, "message": "ok"}


@router.patch("/users/{user_id}")
async def update_user(
    user_id: int,
    body: UserUpdate,
    current_user: OwnerUser,
    db: Session = Depends(get_db),
):
    if user_id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot modify your own account via admin panel")

    u = db.get(User, user_id)
    if not u:
        raise HTTPException(status_code=404, detail="User not found")

    if body.role is not None:
        try:
            u.role = UserRole(body.role)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid role: {body.role}")
    if body.is_active is not None:
        u.is_active = body.is_active
    if body.full_name is not None:
        u.full_name = body.full_name

    db.commit()
    db.refresh(u)
    return {"data": _user_out(u), "message": "User updated"}


@router.delete("/users/{user_id}", status_code=204)
async def delete_user(user_id: int, current_user: OwnerUser, db: Session = Depends(get_db)):
    if user_id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot delete your own account")
    u = db.get(User, user_id)
    if not u:
        raise HTTPException(status_code=404, detail="User not found")
    db.delete(u)
    db.commit()
