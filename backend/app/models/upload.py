"""Upload batch and print job models."""

from __future__ import annotations

import enum
from datetime import datetime
from decimal import Decimal
from typing import List, Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.database import Base


class UploadSource(str, enum.Enum):
    manual = "manual"
    api_push = "api_push"


class UploadStatus(str, enum.Enum):
    processing = "processing"
    completed = "completed"
    failed = "failed"


class UploadBatch(Base):
    __tablename__ = "upload_batches"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    printer_id: Mapped[int] = mapped_column(
        ForeignKey("printers.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    uploaded_by_user_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    source: Mapped[UploadSource] = mapped_column(
        Enum(UploadSource, name="upload_source"),
        nullable=False,
    )
    filename: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    rows_total: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    rows_imported: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    rows_skipped: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    skipped_details: Mapped[list] = mapped_column(
        JSONB, nullable=False, default=list, server_default="[]"
    )
    status: Mapped[UploadStatus] = mapped_column(
        Enum(UploadStatus, name="upload_status"),
        nullable=False,
        default=UploadStatus.processing,
        server_default=UploadStatus.processing.value,
    )

    printer: Mapped["Printer"] = relationship(  # noqa: F821
        "Printer", back_populates="upload_batches"
    )
    print_jobs: Mapped[List["PrintJob"]] = relationship(
        "PrintJob",
        back_populates="upload_batch",
        cascade="all, delete-orphan",
    )


class PrintJob(Base):
    __tablename__ = "print_jobs"
    __table_args__ = (
        UniqueConstraint(
            "printer_id",
            "job_id",
            "recorded_at",
            name="uq_print_jobs_printer_job_recorded",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    printer_id: Mapped[int] = mapped_column(
        ForeignKey("printers.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    upload_batch_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("upload_batches.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    job_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    job_name: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    status: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    owner_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    recorded_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
    arrived_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    printed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    color_mode: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    paper_type: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    paper_size: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    paper_width_mm: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(8, 2), nullable=True
    )
    paper_length_mm: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(8, 2), nullable=True
    )
    paper_gsm: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    matched_paper_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("papers.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    is_duplex: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    copies: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, server_default="1"
    )
    input_pages: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    printed_pages: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    color_pages: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    bw_pages: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    specialty_pages: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    gold_pages: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    silver_pages: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    clear_pages: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    white_pages: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    texture_pages: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    pink_pages: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    blank_pages: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    printed_sheets: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    waste_sheets: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    error_info: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Extended CSV fields — job metadata
    sub_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    jdf_job_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    jdf_job_part_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    logical_printer: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    template: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    imposition_settings: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    media_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    paper_tray: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    print_collation: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    imposed_pages: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    last_printed_page: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    banner_sheet: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    change_output_destination: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    account: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    comments: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    folder: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    tag: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Extended CSV fields — timing
    conversion_start_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    conversion_elapsed: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    rip_start_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    rip_elapsed: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    rasterization_start_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    rasterization_elapsed: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    printing_start_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    printing_elapsed: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    # Extended CSV fields — specialty toner pages
    pa_pages: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    gold_6_pages: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    silver_6_pages: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    white_6_pages: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    pink_6_pages: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Extended CSV fields — raster coverage CMYK
    coverage_k: Mapped[Optional[Decimal]] = mapped_column(Numeric(8, 4), nullable=True)
    coverage_c: Mapped[Optional[Decimal]] = mapped_column(Numeric(8, 4), nullable=True)
    coverage_m: Mapped[Optional[Decimal]] = mapped_column(Numeric(8, 4), nullable=True)
    coverage_y: Mapped[Optional[Decimal]] = mapped_column(Numeric(8, 4), nullable=True)

    # Extended CSV fields — raster coverage specialty #1
    coverage_gld_1: Mapped[Optional[Decimal]] = mapped_column(Numeric(8, 4), nullable=True)
    coverage_slv_1: Mapped[Optional[Decimal]] = mapped_column(Numeric(8, 4), nullable=True)
    coverage_clr_1: Mapped[Optional[Decimal]] = mapped_column(Numeric(8, 4), nullable=True)
    coverage_wht_1: Mapped[Optional[Decimal]] = mapped_column(Numeric(8, 4), nullable=True)
    coverage_cr_1: Mapped[Optional[Decimal]] = mapped_column(Numeric(8, 4), nullable=True)
    coverage_p_1: Mapped[Optional[Decimal]] = mapped_column(Numeric(8, 4), nullable=True)
    coverage_pa_1: Mapped[Optional[Decimal]] = mapped_column(Numeric(8, 4), nullable=True)

    # Extended CSV fields — raster coverage specialty #6
    coverage_gld_6: Mapped[Optional[Decimal]] = mapped_column(Numeric(8, 4), nullable=True)
    coverage_slv_6: Mapped[Optional[Decimal]] = mapped_column(Numeric(8, 4), nullable=True)
    coverage_wht_6: Mapped[Optional[Decimal]] = mapped_column(Numeric(8, 4), nullable=True)
    coverage_p_6: Mapped[Optional[Decimal]] = mapped_column(Numeric(8, 4), nullable=True)

    # Extended CSV fields — raster coverage estimation CMYK
    coverage_est_k: Mapped[Optional[Decimal]] = mapped_column(Numeric(8, 4), nullable=True)
    coverage_est_c: Mapped[Optional[Decimal]] = mapped_column(Numeric(8, 4), nullable=True)
    coverage_est_m: Mapped[Optional[Decimal]] = mapped_column(Numeric(8, 4), nullable=True)
    coverage_est_y: Mapped[Optional[Decimal]] = mapped_column(Numeric(8, 4), nullable=True)

    # Extended CSV fields — raster coverage estimation specialty #1
    coverage_est_gld_1: Mapped[Optional[Decimal]] = mapped_column(Numeric(8, 4), nullable=True)
    coverage_est_slv_1: Mapped[Optional[Decimal]] = mapped_column(Numeric(8, 4), nullable=True)
    coverage_est_clr_1: Mapped[Optional[Decimal]] = mapped_column(Numeric(8, 4), nullable=True)
    coverage_est_wht_1: Mapped[Optional[Decimal]] = mapped_column(Numeric(8, 4), nullable=True)
    coverage_est_cr_1: Mapped[Optional[Decimal]] = mapped_column(Numeric(8, 4), nullable=True)
    coverage_est_p_1: Mapped[Optional[Decimal]] = mapped_column(Numeric(8, 4), nullable=True)
    coverage_est_pa_1: Mapped[Optional[Decimal]] = mapped_column(Numeric(8, 4), nullable=True)

    # Extended CSV fields — raster coverage estimation specialty #6
    coverage_est_gld_6: Mapped[Optional[Decimal]] = mapped_column(Numeric(8, 4), nullable=True)
    coverage_est_slv_6: Mapped[Optional[Decimal]] = mapped_column(Numeric(8, 4), nullable=True)
    coverage_est_wht_6: Mapped[Optional[Decimal]] = mapped_column(Numeric(8, 4), nullable=True)
    coverage_est_p_6: Mapped[Optional[Decimal]] = mapped_column(Numeric(8, 4), nullable=True)

    computed_paper_cost: Mapped[Decimal] = mapped_column(
        Numeric(12, 4), nullable=False, default=Decimal("0"), server_default="0"
    )
    computed_toner_cost: Mapped[Decimal] = mapped_column(
        Numeric(12, 4), nullable=False, default=Decimal("0"), server_default="0"
    )
    computed_total_cost: Mapped[Decimal] = mapped_column(
        Numeric(12, 4), nullable=False, default=Decimal("0"), server_default="0"
    )
    is_waste: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )

    printer: Mapped["Printer"] = relationship(  # noqa: F821
        "Printer", back_populates="print_jobs"
    )
    upload_batch: Mapped[Optional["UploadBatch"]] = relationship(
        "UploadBatch", back_populates="print_jobs"
    )
    matched_paper: Mapped[Optional["Paper"]] = relationship("Paper")  # noqa: F821
