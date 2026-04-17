"""User and refresh token models."""

from __future__ import annotations

import enum
from datetime import datetime
from typing import List, Optional

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.database import Base
from app.models.base import TimestampMixin


class UserRole(str, enum.Enum):
    """Roles supported by PrintSight."""

    owner = "owner"
    print_person = "print_person"


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    email: Mapped[str] = mapped_column(
        String(255), unique=True, index=True, nullable=False
    )
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(
        Enum(UserRole, name="user_role"),
        nullable=False,
        default=UserRole.owner,
        server_default=UserRole.owner.value,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )

    # Relationships
    printers: Mapped[List["Printer"]] = relationship(  # noqa: F821
        "Printer",
        back_populates="owner",
        cascade="all, delete-orphan",
    )
    refresh_tokens: Mapped[List["RefreshToken"]] = relationship(
        "RefreshToken",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    papers: Mapped[List["Paper"]] = relationship(  # noqa: F821
        "Paper",
        back_populates="owner",
        cascade="all, delete-orphan",
    )
    notification_config: Mapped[Optional["NotificationConfig"]] = relationship(  # noqa: F821
        "NotificationConfig",
        back_populates="user",
        cascade="all, delete-orphan",
        uselist=False,
    )
    webhook_configs: Mapped[List["WebhookConfig"]] = relationship(  # noqa: F821
        "WebhookConfig",
        back_populates="owner",
        cascade="all, delete-orphan",
    )


class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    token: Mapped[str] = mapped_column(
        String(512), unique=True, index=True, nullable=False
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    revoked: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    user: Mapped["User"] = relationship("User", back_populates="refresh_tokens")
