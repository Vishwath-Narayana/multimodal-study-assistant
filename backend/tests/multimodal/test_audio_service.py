from __future__ import annotations

import sqlite3
from pathlib import Path

from app.ingestion.models import BlockType
from app.ingestion.repository import ChunkRepository, DocumentRepository
from app.ingestion.storage import DataPaths
from app.multimodal.audio_service import AudioIngestionService
from app.multimodal.errors import AudioValidationError
from app.multimodal.models import TranscriptSegment
from app.multimodal.repository import ArtifactRepository
from tests.multimodal.fakes import FakeTranscriptionProvider


def _service(
    db_conn: sqlite3.Connection, tmp_path: Path, *, provider: FakeTranscriptionProvider
) -> AudioIngestionService:
    return AudioIngestionService(
        transcription_provider=provider,
        document_repo=DocumentRepository(db_conn),
        chunk_repo=ChunkRepository(db_conn),
        artifact_repo=ArtifactRepository(db_conn),
        data_paths=DataPaths(str(tmp_path / "data")),
        supported_extensions=("wav", "mp3", "m4a"),
        max_upload_size_bytes=10_000_000,
        chunk_target_tokens=512,
    )


def test_ingest_wav_succeeds_and_creates_transcript_chunks(
    db_conn: sqlite3.Connection, tmp_path: Path, wav_bytes: bytes
) -> None:
    service = _service(db_conn, tmp_path, provider=FakeTranscriptionProvider())
    result = service.ingest("lecture.wav", wav_bytes)

    assert result.status == "completed"
    assert result.segment_count == 2
    assert result.chunk_count >= 1
    assert result.duplicate is False
    assert result.language == "en"

    chunks = ChunkRepository(db_conn).list_for_document(result.document_id)
    assert all(c.chunk_type == BlockType.TRANSCRIPT for c in chunks)
    assert chunks[0].audio_start == 0.0

    document = DocumentRepository(db_conn).get_by_id(result.document_id)
    assert document is not None
    assert document.status == "completed"
    assert document.file_type == "wav"


def test_ingest_wav_creates_one_audio_artifact(
    db_conn: sqlite3.Connection, tmp_path: Path, wav_bytes: bytes
) -> None:
    service = _service(db_conn, tmp_path, provider=FakeTranscriptionProvider())
    result = service.ingest("lecture.wav", wav_bytes)

    artifacts = ArtifactRepository(db_conn).list_for_document(result.document_id)
    assert len(artifacts) == 1
    assert artifacts[0].artifact_type.value == "audio"
    assert artifacts[0].sha256 is not None


def test_ingest_detects_duplicate(
    db_conn: sqlite3.Connection, tmp_path: Path, wav_bytes: bytes
) -> None:
    service = _service(db_conn, tmp_path, provider=FakeTranscriptionProvider())
    first = service.ingest("lecture.wav", wav_bytes)
    second = service.ingest("lecture_copy.wav", wav_bytes)
    assert second.duplicate is True
    assert second.document_id == first.document_id
    assert second.status == "duplicate"


def test_ingest_without_transcription_provider_fails_explicitly_no_fake_transcript(
    db_conn: sqlite3.Connection, tmp_path: Path, wav_bytes: bytes
) -> None:
    service = _service(db_conn, tmp_path, provider=FakeTranscriptionProvider(available=False))
    result = service.ingest("lecture.wav", wav_bytes)

    assert result.status == "failed"
    assert result.error_message is not None
    assert result.chunk_count == 0
    assert ChunkRepository(db_conn).list_for_document(result.document_id) == []


def test_ingest_when_transcription_fails_marks_document_failed(
    db_conn: sqlite3.Connection, tmp_path: Path, wav_bytes: bytes
) -> None:
    service = _service(db_conn, tmp_path, provider=FakeTranscriptionProvider(fails=True))
    result = service.ingest("lecture.wav", wav_bytes)

    assert result.status == "failed"
    document = DocumentRepository(db_conn).get_by_id(result.document_id)
    assert document is not None
    assert document.status == "failed"
    assert document.error_message


def test_ingest_rejects_invalid_audio_upload(db_conn: sqlite3.Connection, tmp_path: Path) -> None:
    service = _service(db_conn, tmp_path, provider=FakeTranscriptionProvider())
    try:
        service.ingest("notes.txt", b"plain text, not audio")
        raise AssertionError("expected AudioValidationError")
    except AudioValidationError as exc:
        assert "Unsupported" in exc.message


def test_ingest_uses_configured_language(
    db_conn: sqlite3.Connection, tmp_path: Path, wav_bytes: bytes
) -> None:
    provider = FakeTranscriptionProvider(
        segments=[TranscriptSegment(text="Bonjour.", start=0.0, end=1.0)], language="fr"
    )
    service = AudioIngestionService(
        transcription_provider=provider,
        document_repo=DocumentRepository(db_conn),
        chunk_repo=ChunkRepository(db_conn),
        artifact_repo=ArtifactRepository(db_conn),
        data_paths=DataPaths(str(tmp_path / "data")),
        supported_extensions=("wav", "mp3", "m4a"),
        max_upload_size_bytes=10_000_000,
        chunk_target_tokens=512,
        language="fr",
    )
    result = service.ingest("lecture.wav", wav_bytes)
    assert result.language == "fr"
