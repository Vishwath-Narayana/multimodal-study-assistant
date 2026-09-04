"""Ingestion orchestration.

:class:`IngestionService` composes the smaller, independently-testable
steps (validation, hashing, parsing, chunking, persistence) rather than
doing everything itself — see docs/architecture/ingestion.md.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING

from app.ingestion.chunking import ChunkingConfig, chunk_document
from app.ingestion.errors import (
    IngestionError,
    ParserError,
    ResourceLimitExceededError,
    ValidationError,
)
from app.ingestion.hashing import document_id_from_hash, sha256_bytes
from app.ingestion.models import BlockType, ParsedDocument
from app.ingestion.parsers.base import DocumentParser
from app.ingestion.repository import ChunkRepository, DocumentRepository, DocumentUpsert
from app.ingestion.storage import DataPaths, delete_document_files, save_upload
from app.ingestion.validation import validate_upload

if TYPE_CHECKING:
    from app.multimodal.image_processing import ImageEnrichmentService
    from app.multimodal.repository import ArtifactRepository

logger = logging.getLogger(__name__)


@dataclass
class IngestionResult:
    document_id: str
    filename: str
    status: str
    page_count: int | None
    block_count: int
    chunk_count: int
    duplicate: bool
    error_message: str | None = None


class IngestionService:
    def __init__(
        self,
        *,
        parser: DocumentParser,
        document_repo: DocumentRepository,
        chunk_repo: ChunkRepository,
        data_paths: DataPaths,
        supported_extensions: tuple[str, ...],
        max_upload_size_bytes: int,
        chunking_config: ChunkingConfig,
        image_enricher: ImageEnrichmentService | None = None,
        artifact_repo: ArtifactRepository | None = None,
        max_document_pages: int | None = None,
        max_extracted_chars: int | None = None,
        max_chunks_per_document: int | None = None,
    ) -> None:
        self._parser = parser
        self._documents = document_repo
        self._chunks = chunk_repo
        self._paths = data_paths
        self._supported_extensions = supported_extensions
        self._max_upload_size_bytes = max_upload_size_bytes
        self._chunking_config = chunking_config
        # Phase 4: optional, so every existing caller/test that constructs
        # an `IngestionService` without these keeps working unchanged —
        # ingestion without image enrichment configured behaves exactly as
        # it did in Phase 1 (image blocks kept, no OCR/VLM attempted).
        self._image_enricher = image_enricher
        self._artifact_repo = artifact_repo
        # Phase 8 resource ceilings (spec section 8B.2/8C) — all optional
        # (None = unbounded) so every existing test/caller that constructs
        # `IngestionService` directly keeps working unchanged.
        self._max_document_pages = max_document_pages
        self._max_extracted_chars = max_extracted_chars
        self._max_chunks_per_document = max_chunks_per_document

    def ingest(self, filename: str, data: bytes) -> IngestionResult:
        started = time.monotonic()

        validated = validate_upload(
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
                "ingestion.duplicate document_id=%s filename=%s file_hash=%s",
                document_id,
                filename,
                file_hash,
            )
            return IngestionResult(
                document_id=existing.id,
                filename=existing.filename,
                status="duplicate",
                page_count=existing.page_count,
                block_count=existing.block_count or 0,
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

        try:
            save_upload(self._paths, document_id, validated.safe_filename, data)
            parsed = self._parse(document_id, validated.original_filename, file_hash)
            self._enforce_resource_limits(parsed)
            if self._image_enricher is not None:
                parsed.blocks = [
                    self._image_enricher.enrich(document_id, block)
                    if block.type == BlockType.IMAGE
                    else block
                    for block in parsed.blocks
                ]
            chunks = chunk_document(document_id, parsed.blocks, self._chunking_config)
            if (
                self._max_chunks_per_document is not None
                and len(chunks) > self._max_chunks_per_document
            ):
                raise ResourceLimitExceededError(
                    "Document produced more chunks than the allowed limit "
                    f"({self._max_chunks_per_document}); it was not indexed."
                )
            self._chunks.replace_for_document(document_id, chunks)
            if self._artifact_repo is not None:
                for chunk in chunks:
                    if chunk.artifact_id:
                        self._artifact_repo.set_chunk_id(chunk.artifact_id, chunk.id)

            stored = self._documents.upsert(
                DocumentUpsert(
                    id=document_id,
                    filename=validated.original_filename,
                    file_type=validated.file_type,
                    file_hash=file_hash,
                    status="completed",
                    page_count=parsed.metadata.page_count,
                    title=parsed.metadata.title,
                    author=parsed.metadata.author,
                    subject=parsed.metadata.subject,
                    block_count=len(parsed.blocks),
                    chunk_count=len(chunks),
                )
            )

            duration_ms = (time.monotonic() - started) * 1000
            image_count = sum(1 for b in parsed.blocks if b.image_path)
            table_count = sum(1 for b in parsed.blocks if b.table_content is not None)
            logger.info(
                "ingestion.completed document_id=%s filename=%s file_hash=%s "
                "page_count=%s block_count=%d chunk_count=%d image_count=%d "
                "table_count=%d duration_ms=%.1f",
                document_id,
                filename,
                file_hash,
                parsed.metadata.page_count,
                len(parsed.blocks),
                len(chunks),
                image_count,
                table_count,
                duration_ms,
            )

            return IngestionResult(
                document_id=stored.id,
                filename=stored.filename,
                status="completed",
                page_count=stored.page_count,
                block_count=stored.block_count or 0,
                chunk_count=stored.chunk_count or 0,
                duplicate=False,
            )
        except IngestionError as exc:
            self._documents.upsert(
                DocumentUpsert(
                    id=document_id,
                    filename=validated.original_filename,
                    file_type=validated.file_type,
                    file_hash=file_hash,
                    status="failed",
                    error_message=exc.message,
                )
            )
            # Spec section 8B/8K: never leave a failed upload's raw bytes
            # (or any partially-produced processed/ artifacts) on disk —
            # otherwise repeated uploads of different documents that always
            # fail parsing/validation would accumulate disk usage
            # indefinitely. Best-effort: this only ever runs after
            # `save_upload` succeeded, but is safe to call unconditionally.
            delete_document_files(self._paths, document_id)
            logger.warning(
                "ingestion.failed document_id=%s filename=%s error=%s",
                document_id,
                filename,
                exc.message,
            )
            return IngestionResult(
                document_id=document_id,
                filename=filename,
                status="failed",
                page_count=None,
                block_count=0,
                chunk_count=0,
                duplicate=False,
                error_message=exc.message,
            )

    def _enforce_resource_limits(self, parsed: ParsedDocument) -> None:
        """Reject an otherwise-successfully-parsed document that exceeds a
        configured resource ceiling (spec section 8B.2/8C) before it is
        enriched, chunked, or persisted. Raising here (rather than
        truncating silently) keeps ingestion's fail-safe discipline: a
        document is either indexed in full or not indexed at all, never
        partially/silently truncated."""
        page_count = parsed.metadata.page_count
        if (
            self._max_document_pages is not None
            and page_count is not None
            and page_count > self._max_document_pages
        ):
            raise ResourceLimitExceededError(
                f"Document has {page_count} pages, exceeding the allowed limit "
                f"({self._max_document_pages})."
            )

        if self._max_extracted_chars is not None:
            total_chars = sum(len(block.content) for block in parsed.blocks)
            if total_chars > self._max_extracted_chars:
                raise ResourceLimitExceededError(
                    "Document's extracted text exceeds the allowed size limit "
                    f"({self._max_extracted_chars} characters)."
                )

    def _parse(self, document_id: str, filename: str, file_hash: str) -> ParsedDocument:
        file_path = self._paths.raw_file_path(document_id, filename)
        if not self._parser.supports(filename.rsplit(".", 1)[-1].lower()):
            raise ValidationError(f"No parser available for '{filename}'.")
        try:
            return self._parser.parse(
                file_path, document_id=document_id, filename=filename, file_hash=file_hash
            )
        except ParserError:
            raise
        except Exception as exc:  # keep internal detail out of the user-facing message
            raise ParserError(f"Failed to parse document '{filename}'.") from exc
