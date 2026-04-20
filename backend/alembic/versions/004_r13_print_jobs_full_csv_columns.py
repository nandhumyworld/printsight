"""Rev 1.3 — add all remaining CSV columns to print_jobs.

Revision ID: 004
Revises: 003
Create Date: 2026-04-20
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "004"
down_revision = "003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- Job identity / metadata ---
    op.add_column("print_jobs", sa.Column("sub_id", sa.String(100), nullable=True))
    op.add_column("print_jobs", sa.Column("jdf_job_id", sa.String(100), nullable=True))
    op.add_column("print_jobs", sa.Column("jdf_job_part_id", sa.String(100), nullable=True))
    op.add_column("print_jobs", sa.Column("logical_printer", sa.String(255), nullable=True))
    op.add_column("print_jobs", sa.Column("template", sa.String(255), nullable=True))
    op.add_column("print_jobs", sa.Column("imposition_settings", sa.String(100), nullable=True))
    op.add_column("print_jobs", sa.Column("media_name", sa.String(255), nullable=True))
    op.add_column("print_jobs", sa.Column("paper_tray", sa.String(100), nullable=True))
    op.add_column("print_jobs", sa.Column("print_collation", sa.String(50), nullable=True))
    op.add_column("print_jobs", sa.Column("imposed_pages", sa.Integer(), nullable=True))
    op.add_column("print_jobs", sa.Column("last_printed_page", sa.String(255), nullable=True))
    op.add_column("print_jobs", sa.Column("banner_sheet", sa.String(100), nullable=True))
    op.add_column("print_jobs", sa.Column("change_output_destination", sa.String(255), nullable=True))
    op.add_column("print_jobs", sa.Column("account", sa.String(255), nullable=True))
    op.add_column("print_jobs", sa.Column("comments", sa.Text(), nullable=True))
    op.add_column("print_jobs", sa.Column("folder", sa.String(500), nullable=True))
    op.add_column("print_jobs", sa.Column("tag", sa.String(255), nullable=True))

    # --- Timing ---
    op.add_column("print_jobs", sa.Column("conversion_start_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("print_jobs", sa.Column("conversion_elapsed", sa.String(50), nullable=True))
    op.add_column("print_jobs", sa.Column("rip_start_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("print_jobs", sa.Column("rip_elapsed", sa.String(50), nullable=True))
    op.add_column("print_jobs", sa.Column("rasterization_start_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("print_jobs", sa.Column("rasterization_elapsed", sa.String(50), nullable=True))
    op.add_column("print_jobs", sa.Column("printing_start_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("print_jobs", sa.Column("printing_elapsed", sa.String(50), nullable=True))

    # --- Specialty toner pages (new variants) ---
    op.add_column("print_jobs", sa.Column("pa_pages", sa.Integer(), nullable=True))
    op.add_column("print_jobs", sa.Column("gold_6_pages", sa.Integer(), nullable=True))
    op.add_column("print_jobs", sa.Column("silver_6_pages", sa.Integer(), nullable=True))
    op.add_column("print_jobs", sa.Column("white_6_pages", sa.Integer(), nullable=True))
    op.add_column("print_jobs", sa.Column("pink_6_pages", sa.Integer(), nullable=True))

    # --- Raster coverage CMYK ---
    op.add_column("print_jobs", sa.Column("coverage_k", sa.Numeric(8, 4), nullable=True))
    op.add_column("print_jobs", sa.Column("coverage_c", sa.Numeric(8, 4), nullable=True))
    op.add_column("print_jobs", sa.Column("coverage_m", sa.Numeric(8, 4), nullable=True))
    op.add_column("print_jobs", sa.Column("coverage_y", sa.Numeric(8, 4), nullable=True))

    # --- Raster coverage specialty #1 ---
    op.add_column("print_jobs", sa.Column("coverage_gld_1", sa.Numeric(8, 4), nullable=True))
    op.add_column("print_jobs", sa.Column("coverage_slv_1", sa.Numeric(8, 4), nullable=True))
    op.add_column("print_jobs", sa.Column("coverage_clr_1", sa.Numeric(8, 4), nullable=True))
    op.add_column("print_jobs", sa.Column("coverage_wht_1", sa.Numeric(8, 4), nullable=True))
    op.add_column("print_jobs", sa.Column("coverage_cr_1", sa.Numeric(8, 4), nullable=True))
    op.add_column("print_jobs", sa.Column("coverage_p_1", sa.Numeric(8, 4), nullable=True))
    op.add_column("print_jobs", sa.Column("coverage_pa_1", sa.Numeric(8, 4), nullable=True))

    # --- Raster coverage specialty #6 ---
    op.add_column("print_jobs", sa.Column("coverage_gld_6", sa.Numeric(8, 4), nullable=True))
    op.add_column("print_jobs", sa.Column("coverage_slv_6", sa.Numeric(8, 4), nullable=True))
    op.add_column("print_jobs", sa.Column("coverage_wht_6", sa.Numeric(8, 4), nullable=True))
    op.add_column("print_jobs", sa.Column("coverage_p_6", sa.Numeric(8, 4), nullable=True))

    # --- Raster coverage estimation CMYK ---
    op.add_column("print_jobs", sa.Column("coverage_est_k", sa.Numeric(8, 4), nullable=True))
    op.add_column("print_jobs", sa.Column("coverage_est_c", sa.Numeric(8, 4), nullable=True))
    op.add_column("print_jobs", sa.Column("coverage_est_m", sa.Numeric(8, 4), nullable=True))
    op.add_column("print_jobs", sa.Column("coverage_est_y", sa.Numeric(8, 4), nullable=True))

    # --- Raster coverage estimation specialty #1 ---
    op.add_column("print_jobs", sa.Column("coverage_est_gld_1", sa.Numeric(8, 4), nullable=True))
    op.add_column("print_jobs", sa.Column("coverage_est_slv_1", sa.Numeric(8, 4), nullable=True))
    op.add_column("print_jobs", sa.Column("coverage_est_clr_1", sa.Numeric(8, 4), nullable=True))
    op.add_column("print_jobs", sa.Column("coverage_est_wht_1", sa.Numeric(8, 4), nullable=True))
    op.add_column("print_jobs", sa.Column("coverage_est_cr_1", sa.Numeric(8, 4), nullable=True))
    op.add_column("print_jobs", sa.Column("coverage_est_p_1", sa.Numeric(8, 4), nullable=True))
    op.add_column("print_jobs", sa.Column("coverage_est_pa_1", sa.Numeric(8, 4), nullable=True))

    # --- Raster coverage estimation specialty #6 ---
    op.add_column("print_jobs", sa.Column("coverage_est_gld_6", sa.Numeric(8, 4), nullable=True))
    op.add_column("print_jobs", sa.Column("coverage_est_slv_6", sa.Numeric(8, 4), nullable=True))
    op.add_column("print_jobs", sa.Column("coverage_est_wht_6", sa.Numeric(8, 4), nullable=True))
    op.add_column("print_jobs", sa.Column("coverage_est_p_6", sa.Numeric(8, 4), nullable=True))


def downgrade() -> None:
    cols = [
        # estimation specialty #6
        "coverage_est_p_6", "coverage_est_wht_6", "coverage_est_slv_6", "coverage_est_gld_6",
        # estimation specialty #1
        "coverage_est_pa_1", "coverage_est_p_1", "coverage_est_cr_1", "coverage_est_wht_1",
        "coverage_est_clr_1", "coverage_est_slv_1", "coverage_est_gld_1",
        # estimation CMYK
        "coverage_est_y", "coverage_est_m", "coverage_est_c", "coverage_est_k",
        # specialty #6
        "coverage_p_6", "coverage_wht_6", "coverage_slv_6", "coverage_gld_6",
        # specialty #1
        "coverage_pa_1", "coverage_p_1", "coverage_cr_1", "coverage_wht_1",
        "coverage_clr_1", "coverage_slv_1", "coverage_gld_1",
        # CMYK
        "coverage_y", "coverage_m", "coverage_c", "coverage_k",
        # specialty pages
        "pink_6_pages", "white_6_pages", "silver_6_pages", "gold_6_pages", "pa_pages",
        # timing
        "printing_elapsed", "printing_start_at", "rasterization_elapsed", "rasterization_start_at",
        "rip_elapsed", "rip_start_at", "conversion_elapsed", "conversion_start_at",
        # metadata
        "tag", "folder", "comments", "account", "change_output_destination", "banner_sheet",
        "last_printed_page", "imposed_pages", "print_collation", "paper_tray", "media_name",
        "imposition_settings", "template", "logical_printer", "jdf_job_part_id",
        "jdf_job_id", "sub_id",
    ]
    for col in cols:
        op.drop_column("print_jobs", col)
