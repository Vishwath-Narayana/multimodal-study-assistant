"""Phase 8N: temporary/uploaded-file cleanup security tests (spec section 8K).

Covers the three cleanup-on-failure paths added/verified in Phase 8:
document ingestion parser failure, document ingestion resource-limit
rejection, and audio ingestion transcription failure — plus the successful
case, so the tests can't pass by simply never writing a file at all.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.core.config import get_settings
from app.ingestion.repository import ChunkRepository, DocumentRepository, get_connection, init_db
from app.ingestion.service import IngestionService
from app.ingestion.storage import DataPaths
from app.multimodal.audio_service import AudioIngestionService
from app.multimodal.interfaces import TranscriptionProvider
from app.multimodal.models import TranscriptionResult, TranscriptionStatus
from app.multimodal.repository import ArtifactRepository


def _raw_dir_for(document_id: str) -> Path:
    settings = get_settings()
    return Path(settings.data_dir).resolve() / "raw" / document_id


def test_successful_ingestion_keeps_the_raw_file(
    ingestion_service: IngestionService, fixtures_dir: Path
) -> None:
    data = (fixtures_dir / "study_notes.pdf").read_bytes()
    result = ingestion_service.ingest("study_notes.pdf", data)
    assert result.status == "completed"
    assert _raw_dir_for(result.document_id).exists()


def test_parser_failure_cleans_up_the_raw_file(
    ingestion_service: IngestionService, fixtures_dir: Path
) -> None:
    data = (fixtures_dir / "corrupted.pdf").read_bytes()
    result = ingestion_service.ingest("corrupted.pdf", data)
    assert result.status == "failed"
    assert not _raw_dir_for(result.document_id).exists()


def test_resource_limit_rejection_cleans_up_the_raw_file(
    ingestion_service: IngestionService, fixtures_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A document that parses fine but exceeds a configured resource
    ceiling must be cleaned up exactly like a parser failure — it is
    rejected, not partially persisted."""
    ingestion_service._max_document_pages = 0  # any real document exceeds this
    data = (fixtures_dir / "study_notes.pdf").read_bytes()
    result = ingestion_service.ingest("study_notes.pdf", data)
    assert result.status == "failed"
    assert result.error_message is not None
    assert not _raw_dir_for(result.document_id).exists()


class _FailingTranscriptionProvider(TranscriptionProvider):
    def is_available(self) -> bool:
        return True

    def transcribe(self, audio_path: Path, *, language: str | None = None) -> TranscriptionResult:
        return TranscriptionResult(status=TranscriptionStatus.FAILED, segments=[])

    @property
    def model_id(self) -> str:
        return "failing-stub"


def test_audio_transcription_failure_cleans_up_the_raw_file(
    ingestion_env: Path, wav_bytes: bytes
) -> None:
    settings = get_settings()
    data_paths = DataPaths(settings.data_dir)
    conn = get_connection(settings.sqlite_path)
    init_db(conn)

    service = AudioIngestionService(
        transcription_provider=_FailingTranscriptionProvider(),
        document_repo=DocumentRepository(conn),
        chunk_repo=ChunkRepository(conn),
        artifact_repo=ArtifactRepository(conn),
        data_paths=data_paths,
        supported_extensions=("wav",),
        max_upload_size_bytes=10_000_000,
        chunk_target_tokens=512,
    )
    result = service.ingest("lecture.wav", wav_bytes)
    assert result.status == "failed"
    assert not _raw_dir_for(result.document_id).exists()


def test_ingest_never_leaves_a_document_with_completed_status_but_missing_file(
    ingestion_service: IngestionService, fixtures_dir: Path
) -> None:
    """Cross-check: a `failed` document row must never coexist with a
    lingering raw file, and a `completed` one must never be missing its
    raw file — the two states are kept in lockstep by design."""
    ok = ingestion_service.ingest(
        "study_notes.pdf", (fixtures_dir / "study_notes.pdf").read_bytes()
    )
    bad = ingestion_service.ingest("corrupted.pdf", (fixtures_dir / "corrupted.pdf").read_bytes())

    assert ok.status == "completed" and _raw_dir_for(ok.document_id).exists()
    assert bad.status == "failed" and not _raw_dir_for(bad.document_id).exists()
