"""Authentication router — register, login, refresh, logout, me."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
import bcrypt
from jose import jwt
from sqlalchemy.orm import Session

from app.auth.deps import CurrentUser, get_current_user
from app.config import settings
from app.database import get_db
from app.models.user import RefreshToken, User, UserRole
from app.schemas.auth import (
    LoginRequest,
    LogoutRequest,
    MessageResponse,
    RefreshRequest,
    RegisterRequest,
    TokenResponse,
    UpdateProfileRequest,
    UserResponse,
)

router = APIRouter(prefix="/auth", tags=["auth"])


def _hash(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def _verify(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode(), hashed.encode())
    except Exception:
        return False


def _make_access_token(user_id: int) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_expire_minutes)
    return jwt.encode({"sub": str(user_id), "exp": expire}, settings.secret_key, algorithm=settings.algorithm)


def _make_refresh_token(user_id: int) -> str:
    expire = datetime.now(timezone.utc) + timedelta(days=settings.refresh_token_expire_days)
    return jwt.encode({"sub": str(user_id), "exp": expire, "type": "refresh"}, settings.secret_key, algorithm=settings.algorithm)


def _user_response(user: User) -> dict:
    return {
        "id": user.id,
        "email": user.email,
        "full_name": user.full_name,
        "role": user.role.value,
        "is_active": user.is_active,
        "created_at": user.created_at.isoformat(),
    }


@router.post("/register", response_model=UserResponse, status_code=201)
async def register(body: RegisterRequest, db: Session = Depends(get_db)):
    if db.query(User).filter(User.email == body.email).first():
        raise HTTPException(status_code=409, detail="Email already registered")
    user = User(
        email=body.email,
        hashed_password=_hash(body.password),
        full_name=body.full_name,
        role=UserRole.owner,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return _user_response(user)


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == body.email).first()
    if not user or not _verify(body.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account disabled")

    access = _make_access_token(user.id)
    refresh = _make_refresh_token(user.id)
    expire = datetime.now(timezone.utc) + timedelta(days=settings.refresh_token_expire_days)
    db.add(RefreshToken(user_id=user.id, token=refresh, expires_at=expire))
    db.commit()
    return {"access_token": access, "refresh_token": refresh, "token_type": "bearer"}


@router.post("/refresh", response_model=TokenResponse)
async def refresh(body: RefreshRequest, db: Session = Depends(get_db)):
    from jose import JWTError
    try:
        payload = jwt.decode(body.refresh_token, settings.secret_key, algorithms=[settings.algorithm])
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    rt = db.query(RefreshToken).filter(RefreshToken.token == body.refresh_token, RefreshToken.revoked == False).first()
    if not rt or rt.expires_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=401, detail="Refresh token expired or revoked")

    rt.revoked = True
    user_id = int(payload["sub"])
    access = _make_access_token(user_id)
    new_refresh = _make_refresh_token(user_id)
    expire = datetime.now(timezone.utc) + timedelta(days=settings.refresh_token_expire_days)
    db.add(RefreshToken(user_id=user_id, token=new_refresh, expires_at=expire))
    db.commit()
    return {"access_token": access, "refresh_token": new_refresh, "token_type": "bearer"}


@router.post("/logout", response_model=MessageResponse)
async def logout(body: LogoutRequest, db: Session = Depends(get_db)):
    rt = db.query(RefreshToken).filter(RefreshToken.token == body.refresh_token).first()
    if rt:
        rt.revoked = True
        db.commit()
    return {"message": "Logged out"}


@router.get("/me", response_model=UserResponse)
async def me(current_user: CurrentUser):
    return _user_response(current_user)


@router.put("/me", response_model=UserResponse)
async def update_me(body: UpdateProfileRequest, current_user: CurrentUser, db: Session = Depends(get_db)):
    if body.new_password:
        if not body.current_password or not _verify(body.current_password, current_user.hashed_password):
            raise HTTPException(status_code=400, detail="Current password is incorrect")
        current_user.hashed_password = _hash(body.new_password)
    if body.full_name:
        current_user.full_name = body.full_name
    if body.email and body.email != current_user.email:
        if db.query(User).filter(User.email == body.email).first():
            raise HTTPException(status_code=409, detail="Email already taken")
        current_user.email = body.email
    db.commit()
    db.refresh(current_user)
    return _user_response(current_user)
