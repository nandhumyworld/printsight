"""Business rule: a job that printed pages is costed regardless of its status.

Statuses like "Deleted", "Held" or "Error" describe what happened to the job in the
print queue, not whether toner was consumed. If pages came out of the machine, the
toner is spent and must be billed. Only `is_waste` categorisation changes — never
the cost itself.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.models.printer import Printer
from app.models.toner import Toner, TonerType
from app.models.upload import PrintJob


@pytest.fixture
def costed_printer(db_session, test_user):
    p = Printer(
        owner_id=test_user.id,
        name="Deleted Cost Printer",
        column_mapping={
            "job_id": "job_id",
            "recorded_at": "recorded_at",
            "status": "status",
            "printed_pages": "printed_pages",
            "color_pages": "color_pages",
            "bw_pages": "bw_pages",
            "coverage_k": "coverage_k",
        },
    )
    db_session.add(p)
    db_session.commit()
    db_session.refresh(p)

    db_session.add(
        Toner(
            printer_id=p.id,
            toner_color="Black",
            coverage_channel="K",
            toner_type=TonerType.standard,
            price_per_unit=Decimal("50.00"),
            rated_yield_pages=1000,
            reference_coverage_pct=Decimal("5.00"),
        )
    )
    db_session.commit()

    yield p

    db_session.query(PrintJob).filter(PrintJob.printer_id == p.id).delete()
    db_session.query(Toner).filter(Toner.printer_id == p.id).delete()
    db_session.commit()
    db_session.delete(p)
    db_session.commit()


DELETED_BUT_PRINTED_CSV = (
    "job_id,recorded_at,status,printed_pages,color_pages,bw_pages,coverage_k\n"
    "DEL-1,2026-07-24 10:00:00,Deleted,10,4,6,11.7\n"
).encode("utf-8")

DELETED_NEVER_PRINTED_CSV = (
    "job_id,recorded_at,status,printed_pages,color_pages,bw_pages,coverage_k\n"
    "DEL-2,2026-07-24 10:05:00,Deleted,0,0,0,0\n"
).encode("utf-8")


def _import(printer_id, raw):
    from app.services.csv_import_service import import_csv_for_printer

    return import_csv_for_printer(
        printer_id=printer_id,
        raw_bytes=raw,
        filename="deleted.csv",
        source="automated",
        uploaded_by_user_id=None,
    )


def test_deleted_job_that_printed_is_still_charged_toner(costed_printer, db_session):
    """A Deleted job with printed pages consumed toner, so it must carry a cost."""
    _import(costed_printer.id, DELETED_BUT_PRINTED_CSV)

    job = (
        db_session.query(PrintJob)
        .filter(PrintJob.printer_id == costed_printer.id, PrintJob.job_id == "DEL-1")
        .one()
    )
    assert job.status == "Deleted"
    assert job.printed_pages == 10
    assert job.computed_toner_cost > 0


def test_deleted_job_that_never_printed_costs_nothing(costed_printer, db_session):
    """Zero printed pages means no toner was spent — cost stays at zero."""
    _import(costed_printer.id, DELETED_NEVER_PRINTED_CSV)

    job = (
        db_session.query(PrintJob)
        .filter(PrintJob.printer_id == costed_printer.id, PrintJob.job_id == "DEL-2")
        .one()
    )
    assert job.printed_pages == 0
    assert job.computed_toner_cost == 0


def test_deleted_job_is_not_marked_waste(costed_printer, db_session):
    """"Deleted" is its own category, not waste.

    Waste means toner was spent on output that was thrown away (failed, cancelled,
    error). A deleted job is simply a job that was removed from the queue, so it must
    stay non-waste and out of the waste_cost / waste_pct figures.
    """
    _import(costed_printer.id, DELETED_BUT_PRINTED_CSV)

    job = (
        db_session.query(PrintJob)
        .filter(PrintJob.printer_id == costed_printer.id, PrintJob.job_id == "DEL-1")
        .one()
    )
    assert job.is_waste is False
    assert job.computed_toner_cost > 0


def test_deleted_job_cost_is_included_in_totals(costed_printer, db_session):
    """Cost totals must not exclude jobs by status — the sum includes Deleted."""
    from sqlalchemy import func

    _import(costed_printer.id, DELETED_BUT_PRINTED_CSV)

    total = (
        db_session.query(func.coalesce(func.sum(PrintJob.computed_toner_cost), 0))
        .filter(PrintJob.printer_id == costed_printer.id)
        .scalar()
    )
    job_cost = (
        db_session.query(PrintJob.computed_toner_cost)
        .filter(PrintJob.printer_id == costed_printer.id, PrintJob.job_id == "DEL-1")
        .scalar()
    )
    assert total == job_cost > 0
