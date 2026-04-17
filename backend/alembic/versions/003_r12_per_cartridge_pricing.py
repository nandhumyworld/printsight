"""Rev 1.2 — per-cartridge pricing on toner_replacement_logs.

Adds cartridge_price_per_unit, cartridge_rated_yield_pages, cartridge_currency.
Backfills existing rows from the parent toner's current price/yield.
Adds composite index for cartridge-by-date lookup.

Revision ID: 003
Revises: 002
Create Date: 2026-04-17
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "003"
down_revision = "002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add new columns as nullable first (for backfill)
    op.add_column(
        "toner_replacement_logs",
        sa.Column("cartridge_price_per_unit", sa.Numeric(10, 2), nullable=True),
    )
    op.add_column(
        "toner_replacement_logs",
        sa.Column("cartridge_rated_yield_pages", sa.Integer(), nullable=True),
    )
    op.add_column(
        "toner_replacement_logs",
        sa.Column(
            "cartridge_currency",
            sa.String(10),
            nullable=True,
            server_default="INR",
        ),
    )

    # Backfill from parent toner
    op.execute(
        """
        UPDATE toner_replacement_logs trl
        SET cartridge_price_per_unit = t.price_per_unit,
            cartridge_rated_yield_pages = t.rated_yield_pages,
            cartridge_currency = t.currency
        FROM toners t
        WHERE trl.toner_id = t.id
          AND trl.cartridge_price_per_unit IS NULL
        """
    )

    # Now make them NOT NULL (existing rows are backfilled; new rows must provide values)
    op.alter_column(
        "toner_replacement_logs",
        "cartridge_price_per_unit",
        nullable=False,
    )
    op.alter_column(
        "toner_replacement_logs",
        "cartridge_rated_yield_pages",
        nullable=False,
    )
    op.alter_column(
        "toner_replacement_logs",
        "cartridge_currency",
        nullable=False,
    )

    # Composite index for cartridge-by-date lookup
    op.create_index(
        "ix_toner_replacement_printer_toner_date",
        "toner_replacement_logs",
        ["printer_id", "toner_id", "replaced_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_toner_replacement_printer_toner_date",
        table_name="toner_replacement_logs",
    )
    op.drop_column("toner_replacement_logs", "cartridge_currency")
    op.drop_column("toner_replacement_logs", "cartridge_rated_yield_pages")
    op.drop_column("toner_replacement_logs", "cartridge_price_per_unit")
