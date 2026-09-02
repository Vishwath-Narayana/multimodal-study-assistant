"""Document upload and ingestion endpoints.

Kept thin per docs/API.md conventions: request handling and HTTP status
mapping only. All ingestion logic lives in
:class:`app.ingestion.service.IngestionService`.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Generator

from fastapi import APIRouter, Depends, HTTPException, UploadFile

from app.core.config import Settings, get_settings
from app.ingestion.chunking import ChunkingConfig
from app.ingestion.errors import ValidationError
from app.ingestion.parsers.docling_parser import DoclingParser
from app.ingestion.repository import ChunkRepository, DocumentRepository, get_connection, init_db
from app.ingestion.service import IngestionService
from app.ingestion.storage import DataPaths, FileImageStorage
from app.schemas.documents import DocumentListResponse, DocumentResponse, IngestionResultResponse

router = APIRouter(prefix="/documents", tags=["documents"])


def _get_connection(
    settings: Settings = Depends(get_settings),
) -> Generator[sqlite3.Connection, None, None]:
    conn = get_connection(settings.sqlite_path)
    init_db(conn)
    try:
        yield conn
    finally:
        conn.close()


def _get_ingestion_service(
    settings: Settings = Depends(get_settings),
    conn: sqlite3.Connection = Depends(_get_connection),
) -> IngestionService:
    data_paths = DataPaths(settings.data_dir)
    image_storage = FileImageStorage(data_paths)
    parser = DoclingParser(image_storage=image_storage)
    return IngestionService(
        parser=parser,
        document_repo=DocumentRepository(conn),
        chunk_repo=ChunkRepository(conn),
        data_paths=data_paths,
        supported_extensions=tuple(
            ext.strip().lower() for ext in settings.supported_extensions_raw.split(",")
        ),
        max_upload_size_bytes=settings.max_upload_size_mb * 1024 * 1024,
        chunking_config=ChunkingConfig(
            target_tokens=settings.chunk_target_tokens,
            overlap_tokens=settings.chunk_overlap_tokens,
        ),
    )


@router.post("/upload", response_model=IngestionResultResponse)
def upload_document(
    file: UploadFile,
    service: IngestionService = Depends(_get_ingestion_service),
) -> IngestionResultResponse:
    data = file.file.read()
    try:
        result = service.ingest(file.filename or "upload", data)
    except ValidationError as exc:
        raise HTTPException(status_code=400, detail=exc.message) from exc
    return IngestionResultResponse(
        document_id=result.document_id,
        filename=result.filename,
        status=result.status,
        page_count=result.page_count,
        block_count=result.block_count,
        chunk_count=result.chunk_count,
        duplicate=result.duplicate,
        error_message=result.error_message,
    )


@router.get("", response_model=DocumentListResponse)
def list_documents(
    conn: sqlite3.Connection = Depends(_get_connection),
) -> DocumentListResponse:
    documents = DocumentRepository(conn).list_documents()
    return DocumentListResponse(
        documents=[DocumentResponse(**vars(doc)) for doc in documents]
    )


@router.get("/{document_id}", response_model=DocumentResponse)
def get_document(
    document_id: str,
    conn: sqlite3.Connection = Depends(_get_connection),
) -> DocumentResponse:
    document = DocumentRepository(conn).get_by_id(document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found.")
    return DocumentResponse(**vars(document))
