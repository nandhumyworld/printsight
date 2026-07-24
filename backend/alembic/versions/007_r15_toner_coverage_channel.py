"""Rev 1.5 — explicit coverage_channel on toners.

Revision ID: 007
Revises: 006
Create Date: 2026-07-23
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

from app.services.toner_channels import backfill_channel

revision = "007"
down_revision = "006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "toners",
        sa.Column("coverage_channel", sa.String(10), nullable=True),
    )
    conn = op.get_bind()
    rows = conn.execute(
        sa.text("SELECT id, printer_id, toner_color FROM toners ORDER BY id")
    ).fetchall()
    seen: set[tuple[int, str]] = set()
    for row_id, printer_id, toner_color in rows:
        channel = backfill_channel(toner_color)
        if not channel:
            continue
        key = (printer_id, channel)
        if key in seen:
            continue
        seen.add(key)
        conn.execute(
            sa.text("UPDATE toners SET coverage_channel = :c WHERE id = :i"),
            {"c": channel, "i": row_id},
        )
    op.create_unique_constraint(
        "uq_toners_printer_channel", "toners", ["printer_id", "coverage_channel"]
    )


def downgrade() -> None:
    op.drop_constraint("uq_toners_printer_channel", "toners", type_="unique")
    op.drop_column("toners", "coverage_channel")
