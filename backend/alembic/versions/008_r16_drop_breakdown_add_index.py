"""drop computed_toner_cost_breakdown, add (printer_id, recorded_at) index

Revision ID: 008_r16_drop_breakdown_add_index
Revises: 007
Create Date: 2026-07-24
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "008_r16_drop_breakdown_add_index"
down_revision = "007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_column("print_jobs", "computed_toner_cost_breakdown")
    op.create_index(
        "ix_print_jobs_printer_recorded",
        "print_jobs",
        ["printer_id", "recorded_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_print_jobs_printer_recorded", table_name="print_jobs")
    op.add_column(
        "print_jobs",
        sa.Column(
            "computed_toner_cost_breakdown",
            JSONB(),
            nullable=False,
            server_default="{}",
        ),
    )
