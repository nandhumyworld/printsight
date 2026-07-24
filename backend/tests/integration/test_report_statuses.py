"""Integration tests for GET /reports/statuses (dynamic status filter options)."""

from __future__ import annotations

import io

MIXED_STATUS_CSV = (
    "job_id,recorded_at,status,printed_pages,color_pages,bw_pages\n"
    "SJOB-1,2026-07-24 10:00:00,Printing Completed,10,4,6\n"
    "SJOB-2,2026-07-24 10:01:00,Deleted,2,0,2\n"
    "SJOB-3,2026-07-24 10:02:00,Deleted,3,0,3\n"
    "SJOB-4,2026-07-24 10:03:00,RIP Completed,1,0,1\n"
).encode("utf-8")


def _import(client, printer_id):
    files = {"file": ("statuses.csv", io.BytesIO(MIXED_STATUS_CSV), "text/csv")}
    return client.post(
        f"/api/v1/printers/{printer_id}/uploads/import",
        files=files,
        headers={"X-API-Key": "test-ingest-key"},
    )


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def test_statuses_returns_actual_values_from_jobs(
    client, printer_with_status_mapping, owner_token
):
    """The filter options must come from the data, not a hardcoded list.

    Real CSVs carry values like "Printing Completed" and "Deleted", which never
    matched the previously hardcoded completed/failed/cancelled options.
    """
    _import(client, printer_with_status_mapping.id)

    r = client.get(
        f"/api/v1/reports/statuses?printer_ids={printer_with_status_mapping.id}",
        headers=_auth(owner_token),
    )

    assert r.status_code == 200, r.text
    values = [s["value"] for s in r.json()["data"]]
    assert "Printing Completed" in values
    assert "Deleted" in values
    assert "RIP Completed" in values


def test_statuses_are_deduplicated_with_counts(
    client, printer_with_status_mapping, owner_token
):
    """Each status appears once, carrying how many jobs hold it."""
    _import(client, printer_with_status_mapping.id)

    r = client.get(
        f"/api/v1/reports/statuses?printer_ids={printer_with_status_mapping.id}",
        headers=_auth(owner_token),
    )

    data = r.json()["data"]
    deleted = [s for s in data if s["value"] == "Deleted"]
    assert len(deleted) == 1
    assert deleted[0]["count"] == 2


def test_statuses_sorted_by_count_descending(
    client, printer_with_status_mapping, owner_token
):
    """Most common statuses first, so the useful options are at the top."""
    _import(client, printer_with_status_mapping.id)

    r = client.get(
        f"/api/v1/reports/statuses?printer_ids={printer_with_status_mapping.id}",
        headers=_auth(owner_token),
    )

    counts = [s["count"] for s in r.json()["data"]]
    assert counts == sorted(counts, reverse=True)


def test_statuses_requires_auth(client):
    r = client.get("/api/v1/reports/statuses")
    assert r.status_code == 401
