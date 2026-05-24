"""Unit tests for csv_import_service core."""

from __future__ import annotations

import pytest

from app.services.csv_import_service import (
    ImportError as CsvImportError,
    ImportResult,
    import_csv_for_printer,
)


SAMPLE_CSV = (
    "job_id,recorded_at,printed_pages,color_pages,bw_pages\n"
    "JOB-1,2026-05-23 10:00:00,10,4,6\n"
    "JOB-2,2026-05-23 10:05:00,2,0,2\n"
)


def test_returns_import_result_dataclass(db_session, printer_with_mapping):
    result = import_csv_for_printer(
        db=db_session,
        printer_id=printer_with_mapping.id,
        raw_bytes=SAMPLE_CSV.encode("utf-8"),
        filename="test.csv",
        source="automated",
        uploaded_by_user_id=None,
    )
    assert isinstance(result, ImportResult)
    assert result.rows_total == 2
    assert result.rows_imported == 2
    assert result.rows_skipped == 0
    assert result.batch_id > 0


def test_duplicate_repost_imports_zero(db_session, printer_with_mapping):
    args = dict(
        db=db_session,
        printer_id=printer_with_mapping.id,
        raw_bytes=SAMPLE_CSV.encode("utf-8"),
        filename="test.csv",
        source="automated",
        uploaded_by_user_id=None,
    )
    first = import_csv_for_printer(**args)
    second = import_csv_for_printer(**args)
    assert first.rows_imported == 2
    assert second.rows_imported == 0
    assert second.rows_skipped == 2


def test_unparseable_csv_raises_import_error(db_session, printer_with_mapping):
    with pytest.raises(CsvImportError) as exc_info:
        import_csv_for_printer(
            db=db_session,
            printer_id=printer_with_mapping.id,
            raw_bytes=b"\x00\x01not a csv",
            filename="bad.bin",
            source="automated",
            uploaded_by_user_id=None,
        )
    assert exc_info.value.error_code == "INVALID_CSV"
    assert exc_info.value.message


def test_unknown_printer_raises(db_session):
    with pytest.raises(CsvImportError) as exc_info:
        import_csv_for_printer(
            db=db_session,
            printer_id=999999,
            raw_bytes=SAMPLE_CSV.encode("utf-8"),
            filename="t.csv",
            source="automated",
            uploaded_by_user_id=None,
        )
    assert exc_info.value.error_code == "PRINTER_NOT_FOUND"


def test_progress_callback_invoked(db_session, printer_with_mapping):
    seen: list[tuple[int, int]] = []
    import_csv_for_printer(
        db=db_session,
        printer_id=printer_with_mapping.id,
        raw_bytes=SAMPLE_CSV.encode("utf-8"),
        filename="t.csv",
        source="automated",
        uploaded_by_user_id=None,
        progress_callback=lambda done, total: seen.append((done, total)),
    )
    assert seen, "progress_callback was never called"
    assert seen[-1][0] == seen[-1][1]
