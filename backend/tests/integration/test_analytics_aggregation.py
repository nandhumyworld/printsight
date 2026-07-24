"""Integration test: analytics endpoints' SQL aggregation matches manual sums."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

import pytest
from jose import jwt

from app.config import settings
from app.models.upload import PrintJob


@pytest.fixture
def owner_auth_headers(test_user):
    token = jwt.encode(
        {"sub": str(test_user.id)}, settings.secret_key, algorithm=settings.algorithm
    )
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def seeded_jobs(db_session, printer_with_mapping):
    jobs = [
        PrintJob(
            printer_id=printer_with_mapping.id,
            job_id="AGG-1",
            recorded_at=datetime(2026, 5, 1, 10, 0, tzinfo=timezone.utc),
            printed_pages=10,
            color_pages=4,
            bw_pages=6,
            computed_paper_cost=Decimal("1.50"),
            computed_toner_cost=Decimal("2.00"),
            computed_total_cost=Decimal("3.50"),
            is_waste=False,
        ),
        PrintJob(
            printer_id=printer_with_mapping.id,
            job_id="AGG-2",
            recorded_at=datetime(2026, 5, 2, 11, 0, tzinfo=timezone.utc),
            printed_pages=20,
            color_pages=0,
            bw_pages=20,
            computed_paper_cost=Decimal("3.00"),
            computed_toner_cost=Decimal("0.00"),
            computed_total_cost=Decimal("3.00"),
            is_waste=False,
        ),
        PrintJob(
            printer_id=printer_with_mapping.id,
            job_id="AGG-3",
            recorded_at=datetime(2026, 6, 3, 9, 0, tzinfo=timezone.utc),
            printed_pages=5,
            color_pages=5,
            bw_pages=0,
            computed_paper_cost=Decimal("0.75"),
            computed_toner_cost=Decimal("4.25"),
            computed_total_cost=Decimal("5.00"),
            is_waste=True,
        ),
    ]
    db_session.add_all(jobs)
    db_session.commit()
    for j in jobs:
        db_session.refresh(j)
    yield jobs

    db_session.query(PrintJob).filter(
        PrintJob.id.in_([j.id for j in jobs])
    ).delete(synchronize_session=False)
    db_session.commit()


def test_summary_totals_match_manual_sum(
    client, seeded_jobs, owner_auth_headers, printer_with_mapping
):
    resp = client.get(
        f"/api/v1/analytics/summary?period=365d&printer_id={printer_with_mapping.id}",
        headers=owner_auth_headers,
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    expected_total = sum(float(j.computed_total_cost) for j in seeded_jobs)
    assert data["total_cost"] == pytest.approx(round(expected_total, 2), abs=0.01)
    assert data["total_jobs"] == len(seeded_jobs)
