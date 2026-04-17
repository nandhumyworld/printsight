"""Initial schema -- all tables for PrintSight.

Revision ID: 001
Revises: None
Create Date: 2026-04-15
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Tables were created via Base.metadata.create_all() before alembic was used.
    # This migration exists solely as a baseline — stamp and move on.
    pass


def downgrade() -> None:
    # Not reversing the entire initial schema.
    pass
