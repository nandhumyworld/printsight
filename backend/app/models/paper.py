"""Paper configuration model."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.database import Base
from app.models.base import TimestampMixin


class Paper(Base, TimestampMixin):
    __tablename__ = "papers"
    __table_args__ = (
        UniqueConstraint("owner_id", "name", name="uq_papers_owner_name"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    owner_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(500), nullable=False)
    display_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    length_mm: Mapped[Optional[Decimal]] = mapped_column(Numeric(8, 2), nullable=True)
    width_mm: Mapped[Optional[Decimal]] = mapped_column(Numeric(8, 2), nullable=True)
    length_tolerance_mm: Mapped[Decimal] = mapped_column(
        Numeric(6, 2), nullable=False, default=Decimal("2"), server_default="2"
    )
    width_tolerance_mm: Mapped[Decimal] = mapped_column(
        Numeric(6, 2), nullable=False, default=Decimal("2"), server_default="2"
    )
    gsm_min: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    gsm_max: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    counter_multiplier: Mapped[Decimal] = mapped_column(
        Numeric(4, 2), nullable=False, default=Decimal("1.0"), server_default="1.0"
    )
    price_per_sheet: Mapped[Decimal] = mapped_column(Numeric(10, 4), nullable=False)
    currency: Mapped[str] = mapped_column(
        String(10), nullable=False, default="INR", server_default="INR"
    )

    owner: Mapped["User"] = relationship("User", back_populates="papers")  # noqa: F821
    printer_links: Mapped[list["PrinterPaper"]] = relationship(
        "PrinterPaper", back_populates="paper", cascade="all, delete-orphan"
    )


class PrinterPaper(Base):
    __tablename__ = "printer_papers"
    __table_args__ = (
        UniqueConstraint("printer_id", "paper_id", name="uq_printer_papers"),
    )

    printer_id: Mapped[int] = mapped_column(
        ForeignKey("printers.id", ondelete="CASCADE"),
        nullable=False,
        primary_key=True,
    )
    paper_id: Mapped[int] = mapped_column(
        ForeignKey("papers.id", ondelete="CASCADE"),
        nullable=False,
        primary_key=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    printer: Mapped["Printer"] = relationship("Printer", back_populates="paper_links")  # noqa: F821
    paper: Mapped["Paper"] = relationship("Paper", back_populates="printer_links")
