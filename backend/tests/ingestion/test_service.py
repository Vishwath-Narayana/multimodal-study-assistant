"""A, B, C, D, E, F, G, R: end-to-end ingestion via IngestionService."""

from pathlib import Path

from app.ingestion.service import IngestionService


def _read(fixtures_dir: Path, filename: str) -> bytes:
    return (fixtures_dir / filename).read_bytes()


def test_ingest_valid_pdf_succeeds(
    ingestion_service: IngestionService, fixtures_dir: Path
) -> None:
    result = ingestion_service.ingest("study_notes.pdf", _read(fixtures_dir, "study_notes.pdf"))
    assert result.status == "completed"
    assert result.block_count > 0
    assert result.chunk_count > 0
    assert result.duplicate is False


def test_ingest_valid_docx_succeeds(
    ingestion_service: IngestionService, fixtures_dir: Path
) -> None:
    result = ingestion_service.ingest("study_notes.docx", _read(fixtures_dir, "study_notes.docx"))
    assert result.status == "completed"
    assert result.block_count > 0
    assert result.chunk_count > 0


def test_ingest_valid_pptx_succeeds(
    ingestion_service: IngestionService, fixtures_dir: Path
) -> None:
    result = ingestion_service.ingest("study_notes.pptx", _read(fixtures_dir, "study_notes.pptx"))
    assert result.status == "completed"
    assert result.page_count == 2
    assert result.block_count > 0
    assert result.chunk_count > 0


def test_ingest_valid_html_succeeds(
    ingestion_service: IngestionService, fixtures_dir: Path
) -> None:
    result = ingestion_service.ingest("study_notes.html", _read(fixtures_dir, "study_notes.html"))
    assert result.status == "completed"
    assert result.block_count > 0
    assert result.chunk_count > 0


def test_ingest_rejects_unsupported_file_type(ingestion_service: IngestionService) -> None:
    from app.ingestion.errors import ValidationError

    try:
        ingestion_service.ingest("malware.exe", b"not a real document")
        raise AssertionError("expected ValidationError")
    except ValidationError as exc:
        assert "Unsupported" in exc.message


def test_ingest_rejects_empty_file(
    ingestion_service: IngestionService, fixtures_dir: Path
) -> None:
    from app.ingestion.errors import ValidationError

    try:
        ingestion_service.ingest("empty.pdf", _read(fixtures_dir, "empty.pdf"))
        raise AssertionError("expected ValidationError")
    except ValidationError as exc:
        assert "empty" in exc.message


def test_ingest_detects_duplicate_on_second_upload(
    ingestion_service: IngestionService, fixtures_dir: Path
) -> None:
    data = _read(fixtures_dir, "study_notes.html")
    first = ingestion_service.ingest("study_notes.html", data)
    second = ingestion_service.ingest("study_notes.html", data)

    assert first.duplicate is False
    assert second.duplicate is True
    assert second.document_id == first.document_id
    assert second.status == "duplicate"
    # Re-ingestion must not silently re-run parsing/chunking and must
    # return the previously computed counts.
    assert second.chunk_count == first.chunk_count


def test_ingest_same_content_different_filename_is_still_a_duplicate(
    ingestion_service: IngestionService, fixtures_dir: Path
) -> None:
    data = _read(fixtures_dir, "study_notes.html")
    first = ingestion_service.ingest("original_name.html", data)
    second = ingestion_service.ingest("renamed_copy.html", data)
    assert second.duplicate is True
    assert second.document_id == first.document_id


def test_ingest_handles_corrupted_document_without_crashing(
    ingestion_service: IngestionService, fixtures_dir: Path
) -> None:
    result = ingestion_service.ingest("corrupted.pdf", _read(fixtures_dir, "corrupted.pdf"))
    assert result.status == "failed"
    assert result.error_message
    # The failure message must be safe/user-facing, not a raw stack trace.
    assert "Traceback" not in result.error_message
