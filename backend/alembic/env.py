"""Alembic environment configuration.

This module wires the Alembic migration context to the application's
SQLAlchemy ``Base.metadata`` so ``alembic revision --autogenerate`` can detect
schema drift across all registered models.
"""

from __future__ import annotations

import os
import sys
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy import engine_from_config, pool

# Ensure the ``backend`` directory (parent of the ``alembic`` folder) is on the
# Python path so that ``import app.*`` works regardless of where alembic is run.
BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

# Import Base and register every model with Base.metadata.
from app.database import Base, DATABASE_URL  # noqa: E402
from app import models  # noqa: E402, F401

config = context.config

# Override the sqlalchemy.url from the environment. This lets us drive the
# migration target purely from DATABASE_URL without editing alembic.ini.
config.set_main_option(
    "sqlalchemy.url",
    os.getenv("DATABASE_URL", DATABASE_URL).replace("postgres://", "postgresql://", 1),
)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    Emits SQL statements to stdout without requiring a DB-API connection.
    """

    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode with a live DB connection."""

    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            compare_server_default=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
