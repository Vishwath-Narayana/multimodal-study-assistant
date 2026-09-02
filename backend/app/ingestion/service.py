"""Ingestion orchestration.

:class:`IngestionService` composes the smaller, independently-testable
steps (validation, hashing, parsing, chunking, persistence) rather than
doing everything itself — see docs/architecture/ingestion.md.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass

from app.ingestion.chunking import ChunkingConfig, chunk_document
from app.ingestion.errors import IngestionError, ParserError, ValidationError
from app.ingestion.hashing import document_id_from_hash, sha256_bytes
from app.ingestion.models import ParsedDocument
from app.ingestion.parsers.base import DocumentParser
from app.ingestion.repository import ChunkRepository, DocumentRepository, DocumentUpsert
from app.ingestion.storage import DataPaths, save_upload
from app.ingestion.validation import validate_upload

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
    ) -> None:
        self._parser = parser
        self._documents = document_repo
        self._chunks = chunk_repo
        self._paths = data_paths
        self._supported_extensions = supported_extensions
        self._max_upload_size_bytes = max_upload_size_bytes
        self._chunking_config = chunking_config

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
            chunks = chunk_document(document_id, parsed.blocks, self._chunking_config)
            self._chunks.replace_for_document(document_id, chunks)

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
