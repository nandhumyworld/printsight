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
    # Postgres < 16 cannot run ALTER TYPE ... ADD VALUE inside a transaction
    # block; Alembic's online runner opens one by default. COMMIT first to
    # close it, then extend the enum. Safe on all supported Postgres versions.
    op.execute("COMMIT")
    op.execute("ALTER TYPE upload_source ADD VALUE IF NOT EXISTS 'automated'")


def downgrade() -> None:
    # No-op: Postgres doesn't support removing enum values without recreating
    # the type. Downgrade leaves the value in place; existing rows referencing
    # it would break a true removal.
    pass
