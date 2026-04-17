"""Toner and toner replacement log models."""

from __future__ import annotations

import enum
from datetime import datetime
from decimal import Decimal
from typing import List, Optional

from sqlalchemy import (
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.database import Base
from app.models.base import TimestampMixin


class TonerType(str, enum.Enum):
    standard = "standard"
    specialty = "specialty"


class Toner(Base, TimestampMixin):
    __tablename__ = "toners"
    __table_args__ = (
        UniqueConstraint("printer_id", "toner_color", name="uq_toners_printer_color"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    printer_id: Mapped[int] = mapped_column(
        ForeignKey("printers.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    toner_color: Mapped[str] = mapped_column(String(50), nullable=False)
    toner_type: Mapped[TonerType] = mapped_column(
        Enum(TonerType, name="toner_type"),
        nullable=False,
        default=TonerType.standard,
        server_default=TonerType.standard.value,
    )
    price_per_unit: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    rated_yield_pages: Mapped[int] = mapped_column(Integer, nullable=False)
    currency: Mapped[str] = mapped_column(
        String(10), nullable=False, default="INR", server_default="INR"
    )

    printer: Mapped["Printer"] = relationship("Printer", back_populates="toners")  # noqa: F821
    replacement_logs: Mapped[List["TonerReplacementLog"]] = relationship(
        "TonerReplacementLog",
        back_populates="toner",
        cascade="all, delete-orphan",
    )


class TonerReplacementLog(Base):
    __tablename__ = "toner_replacement_logs"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    printer_id: Mapped[int] = mapped_column(
        ForeignKey("printers.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    toner_id: Mapped[int] = mapped_column(
        ForeignKey("toners.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    replaced_by_user_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    counter_reading_at_replacement: Mapped[int] = mapped_column(
        Integer, nullable=False
    )
    replaced_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    cartridge_price_per_unit: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), nullable=False
    )
    cartridge_rated_yield_pages: Mapped[int] = mapped_column(Integer, nullable=False)
    cartridge_currency: Mapped[str] = mapped_column(
        String(10), nullable=False, default="INR", server_default="INR"
    )
    actual_yield_pages: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    yield_efficiency_pct: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(6, 2), nullable=True
    )
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    toner: Mapped["Toner"] = relationship("Toner", back_populates="replacement_logs")
