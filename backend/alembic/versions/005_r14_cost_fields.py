"""Rev 1.4 — reference coverage on toners + cost breakdown on print_jobs.

Revision ID: 005
Revises: 004
Create Date: 2026-04-20
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "005"
down_revision = "004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "toners",
        sa.Column(
            "reference_coverage_pct",
            sa.Numeric(5, 2),
            nullable=False,
            server_default="5.00",
        ),
    )
    op.add_column(
        "toner_replacement_logs",
        sa.Column(
            "cartridge_reference_coverage_pct",
            sa.Numeric(5, 2),
            nullable=False,
            server_default="5.00",
        ),
    )
    op.add_column(
        "print_jobs",
        sa.Column(
            "computed_toner_cost_breakdown",
            JSONB,
            nullable=False,
            server_default="{}",
        ),
    )
    op.add_column(
        "print_jobs",
        sa.Column("cost_computed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "print_jobs",
        sa.Column("cost_computation_source", sa.String(20), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("print_jobs", "cost_computation_source")
    op.drop_column("print_jobs", "cost_computed_at")
    op.drop_column("print_jobs", "computed_toner_cost_breakdown")
    op.drop_column("toner_replacement_logs", "cartridge_reference_coverage_pct")
    op.drop_column("toners", "reference_coverage_pct")
