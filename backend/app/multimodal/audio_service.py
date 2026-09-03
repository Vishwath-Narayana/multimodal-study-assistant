"""Audio ingestion orchestration (spec section 14).

Pipeline: validate -> hash/dedupe -> save -> transcribe -> timestamp-aware
chunk -> persist. Deliberately reuses `app.ingestion`'s `DocumentRepository`
/`ChunkRepository`/`DataPaths`/hashing rather than a second, parallel
persistence layer — an audio "document" is just another row in the same
`documents` table (`file_type` one of `wav`/`mp3`/`m4a`), and its transcript
chunks are just `Chunk` rows with `chunk_type == BlockType.TRANSCRIPT`, so
they flow through the existing BM25/FAISS indexing and `/chat/query`
pipeline unchanged (spec section 3: "do not create a completely separate
RAG system").

Unlike image artifacts (one artifact -> one chunk, see
`app.multimodal.image_processing`), one audio artifact produces *many*
transcript chunks — `artifacts.chunk_id` stays `None` for an audio artifact
(a single FK cannot represent "all of these chunks"); the artifact is still
never orphaned because every transcript chunk carries `audio_start`/
`audio_end` plus `document_id`, which is sufficient to trace back to the
one audio artifact for that document (`ArtifactRepository.list_for_document`).
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass

from app.ingestion.errors import StorageError
from app.ingestion.hashing import document_id_from_hash, sha256_bytes
from app.ingestion.repository import ChunkRepository, DocumentRepository, DocumentUpsert
from app.ingestion.storage import DataPaths, save_upload
from app.multimodal.audio_chunking import chunk_transcript
from app.multimodal.interfaces import TranscriptionProvider
from app.multimodal.models import Artifact, ArtifactType, TranscriptionStatus
from app.multimodal.repository import ArtifactRepository
from app.multimodal.security import validate_audio_upload

logger = logging.getLogger(__name__)


@dataclass
class AudioIngestionResult:
    document_id: str
    filename: str
    status: str
    segment_count: int
    chunk_count: int
    duplicate: bool
    language: str | None = None
    error_message: str | None = None


class AudioIngestionService:
    def __init__(
        self,
        *,
        transcription_provider: TranscriptionProvider,
        document_repo: DocumentRepository,
        chunk_repo: ChunkRepository,
        artifact_repo: ArtifactRepository,
        data_paths: DataPaths,
        supported_extensions: tuple[str, ...],
        max_upload_size_bytes: int,
        chunk_target_tokens: int,
        language: str | None = None,
    ) -> None:
        self._transcription = transcription_provider
        self._documents = document_repo
        self._chunks = chunk_repo
        self._artifacts = artifact_repo
        self._paths = data_paths
        self._supported_extensions = supported_extensions
        self._max_upload_size_bytes = max_upload_size_bytes
        self._chunk_target_tokens = chunk_target_tokens
        self._language = language or None

    def ingest(self, filename: str, data: bytes) -> AudioIngestionResult:
        started = time.monotonic()

        validated = validate_audio_upload(
            filename,
            data,
            supported_extensions=self._supported_extensions,
            max_size_bytes=self._max_upload_size_bytes,
        )

        file_hash = sha256_bytes(data)
        document_id = document_id_from_hash(file_hash)

        existing = self._documents.get_by_id(document_id)
        if existing is not None and existing.status == "completed":
            logger.info(
                "audio_ingestion.duplicate document_id=%s filename=%s", document_id, filename
            )
            return AudioIngestionResult(
                document_id=existing.id,
                filename=existing.filename,
                status="duplicate",
                segment_count=existing.block_count or 0,
                chunk_count=existing.chunk_count or 0,
                duplicate=True,
            )

        self._documents.upsert(
            DocumentUpsert(
                id=document_id,
                filename=validated.original_filename,
                file_type=validated.file_type,
                file_hash=file_hash,
                status="processing",
            )
        )

        if not self._transcription.is_available():
            return self._fail(
                document_id,
                validated.original_filename,
                validated.file_type,
                file_hash,
                "No transcription provider is configured/reachable. "
                "Set TRANSCRIPTION_PROVIDER=whisper and ensure the model can load.",
            )

        try:
            save_upload(self._paths, document_id, validated.safe_filename, data)
        except StorageError as exc:
            return self._fail(
                document_id,
                validated.original_filename,
                validated.file_type,
                file_hash,
                exc.message,
            )

        audio_path = self._paths.raw_file_path(document_id, validated.safe_filename)
        result = self._transcription.transcribe(audio_path, language=self._language)

        if result.status != TranscriptionStatus.AVAILABLE:
            reason = (
                "Transcription failed."
                if result.status == TranscriptionStatus.FAILED
                else "Transcription provider became unavailable during processing."
            )
            return self._fail(
                document_id, validated.original_filename, validated.file_type, file_hash, reason
            )

        chunks = chunk_transcript(
            document_id, result.segments, target_tokens=self._chunk_target_tokens
        )
        self._chunks.replace_for_document(document_id, chunks)

        self._artifacts.create(
            Artifact(
                id=f"{document_id}::artifact::audio",
                document_id=document_id,
                artifact_type=ArtifactType.AUDIO,
                storage_path=str(audio_path.relative_to(self._paths.root)),
                mime_type=f"audio/{validated.file_type}",
                sha256=file_hash,
                metadata={
                    "model": result.model,
                    "language": result.language,
                    "segment_count": len(result.segments),
                },
            )
        )

        stored = self._documents.upsert(
            DocumentUpsert(
                id=document_id,
                filename=validated.original_filename,
                file_type=validated.file_type,
                file_hash=file_hash,
                status="completed",
                block_count=len(result.segments),
                chunk_count=len(chunks),
            )
        )

        duration_ms = (time.monotonic() - started) * 1000
        logger.info(
            "audio_ingestion.completed document_id=%s filename=%s segment_count=%d "
            "chunk_count=%d duration_ms=%.1f",
            document_id,
            filename,
            len(result.segments),
            len(chunks),
            duration_ms,
        )

        return AudioIngestionResult(
            document_id=stored.id,
            filename=stored.filename,
            status="completed",
            segment_count=len(result.segments),
            chunk_count=len(chunks),
            duplicate=False,
            language=result.language,
        )

    def _fail(
        self, document_id: str, filename: str, file_type: str, file_hash: str, message: str
    ) -> AudioIngestionResult:
        self._documents.upsert(
            DocumentUpsert(
                id=document_id,
                filename=filename,
                file_type=file_type,
                file_hash=file_hash,
                status="failed",
                error_message=message,
            )
        )
        logger.warning("audio_ingestion.failed document_id=%s error=%s", document_id, message)
        return AudioIngestionResult(
            document_id=document_id,
            filename=filename,
            status="failed",
            segment_count=0,
            chunk_count=0,
            duplicate=False,
            error_message=message,
        )
