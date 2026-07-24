"""Integration test: cost is computed inline during CSV ingest."""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.models.printer import Printer
from app.models.toner import Toner, TonerType


@pytest.fixture
def seeded_printer_with_k_toner(db_session, test_user):
    p = Printer(
        owner_id=test_user.id,
        name="Cost Test Printer",
        column_mapping={
            "job_id": "job_id",
            "recorded_at": "recorded_at",
            "printed_pages": "printed_pages",
            "color_pages": "color_pages",
            "bw_pages": "bw_pages",
            "coverage_k": "coverage_k",
        },
    )
    db_session.add(p)
    db_session.commit()
    db_session.refresh(p)

    toner = Toner(
        printer_id=p.id,
        toner_color="Black",
        coverage_channel="K",
        toner_type=TonerType.standard,
        price_per_unit=Decimal("50.00"),
        rated_yield_pages=1000,
        reference_coverage_pct=Decimal("5.00"),
    )
    db_session.add(toner)
    db_session.commit()

    yield p

    db_session.query(Toner).filter(Toner.printer_id == p.id).delete()
    db_session.delete(p)
    db_session.commit()


@pytest.fixture
def sample_csv_bytes():
    return (
        "job_id,recorded_at,printed_pages,color_pages,bw_pages,coverage_k\n"
        "JOB-1,2026-05-23 10:00:00,10,4,6,11.7\n"
    ).encode("utf-8")


def test_ingest_computes_toner_cost(seeded_printer_with_k_toner, sample_csv_bytes):
    from app.services.csv_import_service import import_csv_for_printer
    from app.models.upload import PrintJob
    from app.database import SessionLocal

    result = import_csv_for_printer(
        printer_id=seeded_printer_with_k_toner.id,
        raw_bytes=sample_csv_bytes,
        filename="t.csv",
        source="automated",
        uploaded_by_user_id=None,
    )
    assert result.rows_imported == 1

    s = SessionLocal()
    try:
        job = s.query(PrintJob).filter_by(printer_id=seeded_printer_with_k_toner.id).one()
        assert float(job.computed_toner_cost) > 0
        assert job.coverage_est_k is not None and float(job.coverage_est_k) > 0
        assert float(job.computed_total_cost) == pytest.approx(
            float(job.computed_paper_cost) + float(job.computed_toner_cost), abs=1e-6
        )
    finally:
        s.close()
