"""Rev 1.1 — printer image_url, paper tolerances, printer_papers junction,
print_jobs.paper_gsm, print_jobs.matched_paper_id.

Revision ID: 002
Revises: 001
Create Date: 2026-04-17
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # printers: add image_url
    op.add_column("printers", sa.Column("image_url", sa.String(500), nullable=True))

    # papers: add tolerances
    op.add_column(
        "papers",
        sa.Column(
            "length_tolerance_mm",
            sa.Numeric(6, 2),
            nullable=False,
            server_default="2",
        ),
    )
    op.add_column(
        "papers",
        sa.Column(
            "width_tolerance_mm",
            sa.Numeric(6, 2),
            nullable=False,
            server_default="2",
        ),
    )

    # print_jobs: add paper_gsm and matched_paper_id
    op.add_column("print_jobs", sa.Column("paper_gsm", sa.Integer(), nullable=True))
    op.add_column(
        "print_jobs",
        sa.Column("matched_paper_id", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        "fk_print_jobs_matched_paper",
        "print_jobs",
        "papers",
        ["matched_paper_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_print_jobs_matched_paper_id", "print_jobs", ["matched_paper_id"]
    )

    # printer_papers junction table — may already exist if DB was create_all'd
    conn = op.get_bind()
    result = conn.execute(
        sa.text("SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name='printer_papers')")
    )
    if not result.scalar():
        op.create_table(
            "printer_papers",
            sa.Column(
                "printer_id",
                sa.Integer(),
                sa.ForeignKey("printers.id", ondelete="CASCADE"),
                nullable=False,
                primary_key=True,
            ),
            sa.Column(
                "paper_id",
                sa.Integer(),
                sa.ForeignKey("papers.id", ondelete="CASCADE"),
                nullable=False,
                primary_key=True,
            ),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                nullable=False,
            ),
            sa.UniqueConstraint("printer_id", "paper_id", name="uq_printer_papers"),
        )


def downgrade() -> None:
    op.drop_table("printer_papers")
    op.drop_index("ix_print_jobs_matched_paper_id", table_name="print_jobs")
    op.drop_constraint("fk_print_jobs_matched_paper", "print_jobs", type_="foreignkey")
    op.drop_column("print_jobs", "matched_paper_id")
    op.drop_column("print_jobs", "paper_gsm")
    op.drop_column("papers", "width_tolerance_mm")
    op.drop_column("papers", "length_tolerance_mm")
    op.drop_column("printers", "image_url")
