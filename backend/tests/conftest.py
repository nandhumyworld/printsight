"""Shared pytest fixtures."""

from __future__ import annotations

import os
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.config import get_settings, settings
from app.database import Base
from app.main import app
from app.models.printer import Printer
from app.models.upload import PrintJob, UploadBatch
from app.models.user import User, UserRole


# Use a separate test DB if TEST_DATABASE_URL is set, otherwise reuse dev DB.
TEST_DB_URL = os.environ.get("TEST_DATABASE_URL", settings.database_url)


@pytest.fixture(scope="session")
def engine():
    eng = create_engine(TEST_DB_URL)
    Base.metadata.create_all(bind=eng)
    yield eng
    eng.dispose()


@pytest.fixture
def db_session(engine):
    Session = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    s = Session()
    try:
        yield s
    finally:
        s.rollback()
        s.close()


@pytest.fixture
def test_user(db_session) -> User:
    # NOTE: UserRole has only `owner` and `print_person` in this project — not `admin`.
    u = User(
        email=f"ingest-test-{os.getpid()}@example.com",
        hashed_password="x",
        full_name="Ingest Test",
        role=UserRole.owner,
        is_active=True,
    )
    db_session.add(u)
    db_session.commit()
    db_session.refresh(u)
    yield u
    db_session.delete(u)
    db_session.commit()


@pytest.fixture
def printer_with_mapping(db_session, test_user) -> Printer:
    p = Printer(
        owner_id=test_user.id,
        name="Test Printer",
        column_mapping={
            "job_id": "job_id",
            "recorded_at": "recorded_at",
            "printed_pages": "printed_pages",
            "color_pages": "color_pages",
            "bw_pages": "bw_pages",
        },
    )
    db_session.add(p)
    db_session.commit()
    db_session.refresh(p)
    yield p
    db_session.delete(p)
    db_session.commit()


@pytest.fixture
def second_printer(db_session, test_user) -> Printer:
    p = Printer(owner_id=test_user.id, name="Other Printer", column_mapping={})
    db_session.add(p)
    db_session.commit()
    db_session.refresh(p)
    yield p
    db_session.delete(p)
    db_session.commit()


@pytest.fixture
def printer_with_status_mapping(db_session, test_user) -> Printer:
    """Printer whose column mapping includes `status`, for report status filtering."""
    p = Printer(
        owner_id=test_user.id,
        name="Status Printer",
        column_mapping={
            "job_id": "job_id",
            "recorded_at": "recorded_at",
            "status": "status",
            "printed_pages": "printed_pages",
            "color_pages": "color_pages",
            "bw_pages": "bw_pages",
        },
    )
    db_session.add(p)
    db_session.commit()
    db_session.refresh(p)
    yield p
    db_session.query(PrintJob).filter(PrintJob.printer_id == p.id).delete()
    db_session.query(UploadBatch).filter(UploadBatch.printer_id == p.id).delete()
    db_session.commit()
    db_session.delete(p)
    db_session.commit()


@pytest.fixture
def print_person_user(db_session) -> User:
    u = User(
        email=f"printer-person-{os.getpid()}@example.com",
        hashed_password="x",
        full_name="Print Person",
        role=UserRole.print_person,
        is_active=True,
    )
    db_session.add(u)
    db_session.commit()
    db_session.refresh(u)
    yield u
    db_session.delete(u)
    db_session.commit()


@pytest.fixture
def owner_token(test_user) -> str:
    from app.routers.auth import _make_access_token

    return _make_access_token(test_user.id)


@pytest.fixture
def print_person_token(print_person_user) -> str:
    from app.routers.auth import _make_access_token

    return _make_access_token(print_person_user.id)


@pytest.fixture(autouse=True)
def _ingest_key_env(monkeypatch):
    """Set a known ingest key for all tests; clear cached settings."""
    monkeypatch.setenv("INGEST_API_KEY", "test-ingest-key")
    get_settings.cache_clear()


@pytest.fixture
def client():
    return TestClient(app)
