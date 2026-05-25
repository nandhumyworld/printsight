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
    # block; Alembic's online runner opens one by default. autocommit_block
    # scopes the COMMIT to just this statement so the surrounding migration
    # transaction is not poisoned for any subsequent migrations in the run.
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE upload_source ADD VALUE IF NOT EXISTS 'automated'")


def downgrade() -> None:
    # No-op: Postgres doesn't support removing enum values without recreating
    # the type. Downgrade leaves the value in place; existing rows referencing
    # it would break a true removal.
    pass
