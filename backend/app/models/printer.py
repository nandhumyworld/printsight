"""Printer and printer API key models."""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.database import Base
from app.models.base import TimestampMixin


class Printer(Base, TimestampMixin):
    __tablename__ = "printers"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    owner_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    model: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    type: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    serial_number: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    location: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    column_mapping: Mapped[dict] = mapped_column(
        JSONB, nullable=False, default=dict, server_default="{}"
    )
    image_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )

    # Relationships
    owner: Mapped["User"] = relationship("User", back_populates="printers")  # noqa: F821
    api_keys: Mapped[List["PrinterApiKey"]] = relationship(
        "PrinterApiKey",
        back_populates="printer",
        cascade="all, delete-orphan",
    )
    toners: Mapped[List["Toner"]] = relationship(  # noqa: F821
        "Toner",
        back_populates="printer",
        cascade="all, delete-orphan",
    )
    upload_batches: Mapped[List["UploadBatch"]] = relationship(  # noqa: F821
        "UploadBatch",
        back_populates="printer",
        cascade="all, delete-orphan",
    )
    print_jobs: Mapped[List["PrintJob"]] = relationship(  # noqa: F821
        "PrintJob",
        back_populates="printer",
        cascade="all, delete-orphan",
    )
    paper_links: Mapped[List["PrinterPaper"]] = relationship(  # noqa: F821
        "PrinterPaper",
        back_populates="printer",
        cascade="all, delete-orphan",
    )


class PrinterApiKey(Base):
    __tablename__ = "printer_api_keys"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    printer_id: Mapped[int] = mapped_column(
        ForeignKey("printers.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    owner_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    key_prefix: Mapped[str] = mapped_column(String(12), nullable=False, index=True)
    key_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    label: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    last_used_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    printer: Mapped["Printer"] = relationship("Printer", back_populates="api_keys")
