"""Integration tests for upload history detail + owner-only batch delete."""

from __future__ import annotations

import io

from app.models.upload import PrintJob, UploadBatch

SAMPLE_CSV = (
    "job_id,recorded_at,printed_pages,color_pages,bw_pages\n"
    "HJOB-1,2026-07-24 10:00:00,10,4,6\n"
    "HJOB-2,2026-07-24 10:05:00,2,0,2\n"
).encode("utf-8")

BAD_ROW_CSV = (
    "job_id,recorded_at,printed_pages,color_pages,bw_pages\n"
    ",2026-07-24 11:00:00,5,1,4\n"
).encode("utf-8")


def _import(client, printer_id, body=SAMPLE_CSV, filename="hist.csv"):
    files = {"file": (filename, io.BytesIO(body), "text/csv")}
    return client.post(
        f"/api/v1/printers/{printer_id}/uploads/import",
        files=files,
        headers={"X-API-Key": "test-ingest-key"},
    )


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def test_batch_detail_returns_skipped_details(client, printer_with_mapping, owner_token):
    """A skipped row's reason must be readable from the batch detail endpoint."""
    batch_id = _import(client, printer_with_mapping.id, body=BAD_ROW_CSV).json()["batch_id"]

    r = client.get(
        f"/api/v1/printers/{printer_with_mapping.id}/uploads/{batch_id}",
        headers=_auth(owner_token),
    )

    assert r.status_code == 200, r.text
    d = r.json()["data"]
    assert d["rows_skipped"] == 1
    assert d["source"] == "automated"
    assert d["skipped_details"] == [{"row_number": 2, "reason": "Missing job_id"}]


def test_batch_detail_of_another_printer_returns_404(
    client, printer_with_mapping, second_printer, owner_token
):
    """A batch must not be readable through a different printer's path."""
    batch_id = _import(client, printer_with_mapping.id).json()["batch_id"]

    r = client.get(
        f"/api/v1/printers/{second_printer.id}/uploads/{batch_id}",
        headers=_auth(owner_token),
    )

    assert r.status_code == 404


def test_delete_batch_preserves_print_jobs(
    client, printer_with_mapping, owner_token, db_session
):
    """Deleting a batch row must orphan its print jobs, never delete them.

    Regression guard: UploadBatch.print_jobs declares cascade="all, delete-orphan",
    so an ORM delete would destroy the imported jobs. Only a bulk query delete
    honours the DB-level ondelete="SET NULL".
    """
    batch_id = _import(client, printer_with_mapping.id).json()["batch_id"]
    jobs_before = (
        db_session.query(PrintJob)
        .filter(PrintJob.printer_id == printer_with_mapping.id)
        .count()
    )
    assert jobs_before == 2

    r = client.delete(
        f"/api/v1/printers/{printer_with_mapping.id}/uploads/{batch_id}",
        headers=_auth(owner_token),
    )

    assert r.status_code == 200, r.text
    assert r.json()["data"]["jobs_preserved"] == 2

    db_session.expire_all()
    assert db_session.get(UploadBatch, batch_id) is None
    surviving = (
        db_session.query(PrintJob)
        .filter(PrintJob.printer_id == printer_with_mapping.id)
        .all()
    )
    assert len(surviving) == 2
    assert all(j.upload_batch_id is None for j in surviving)


def test_delete_batch_requires_owner(
    client, printer_with_mapping, print_person_token, db_session
):
    """A print_person must not be able to delete upload history."""
    batch_id = _import(client, printer_with_mapping.id).json()["batch_id"]

    r = client.delete(
        f"/api/v1/printers/{printer_with_mapping.id}/uploads/{batch_id}",
        headers=_auth(print_person_token),
    )

    assert r.status_code == 403
    db_session.expire_all()
    assert db_session.get(UploadBatch, batch_id) is not None


def test_list_uploads_includes_source(client, printer_with_mapping, owner_token):
    """The list response must carry `source` so the UI can badge automated imports."""
    _import(client, printer_with_mapping.id)

    r = client.get(
        f"/api/v1/printers/{printer_with_mapping.id}/uploads",
        headers=_auth(owner_token),
    )

    assert r.status_code == 200, r.text
    assert r.json()["data"][0]["source"] == "automated"
