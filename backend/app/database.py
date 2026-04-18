"""Database connection layer for PrintSight.

Provides the SQLAlchemy engine, session factory, declarative ``Base`` and the
``get_db`` FastAPI dependency. This module intentionally keeps the database
bootstrap logic self-contained so Alembic and the FastAPI app can share the
same configuration.
"""

from __future__ import annotations

import os
from typing import Generator

from dotenv import load_dotenv
load_dotenv()

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

# Read database URL from environment. A local-dev fallback is provided so that
# engineers can run the backend without setting env vars explicitly.
DATABASE_URL: str = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:postgres@localhost:5432/printsight",
).replace("postgres://", "postgresql://", 1)

# ``pool_pre_ping`` enables liveness checks to avoid stale-connection errors
# after the database restarts or a firewall closes idle sockets.
engine = create_engine(DATABASE_URL, pool_pre_ping=True, future=True)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
    expire_on_commit=False,
    class_=Session,
)


class Base(DeclarativeBase):
    """Base declarative class for all ORM models."""


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency that yields a database session.

    The session is always closed at the end of the request, even when an
    exception is raised by the route handler.
    """

    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
