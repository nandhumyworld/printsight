"""Rev 1.5 — extend upload_source enum with 'automated'.

Revision ID: 006
Revises: 005
Create Date: 2026-05-24
"""

from __future__ import annotations

from alembic import op

revision = "006"
down_revision = "005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TYPE upload_source ADD VALUE IF NOT EXISTS 'automated'")


def downgrade() -> None:
    pass
