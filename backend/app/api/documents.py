"""Document (and, as of Phase 4, audio) upload/ingestion endpoints.

Kept thin per docs/API.md conventions: request handling and HTTP status
mapping only. All ingestion logic lives in
:class:`app.ingestion.service.IngestionService` (documents) and
:class:`app.multimodal.audio_service.AudioIngestionService` (audio).

`POST /documents/upload` stays a single endpoint for every supported
modality (spec section 25: "do not create unnecessary endpoints") — it
dispatches to the audio pipeline when the upload's extension is one of
`Settings.audio_supported_extensions_raw`, and to the existing Docling
pipeline otherwise. Both pipelines report through the same
`IngestionResultResponse` shape.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Generator

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from fastapi.responses import FileResponse

from app.core.config import Settings, get_settings
from app.ingestion.chunking import ChunkingConfig
from app.ingestion.errors import StorageError, ValidationError
from app.ingestion.parsers.docling_parser import DoclingParser
from app.ingestion.repository import ChunkRepository, DocumentRepository, get_connection, init_db
from app.ingestion.service import IngestionService
from app.ingestion.storage import DataPaths, FileImageStorage, delete_document_files
from app.multimodal.audio_service import AudioIngestionResult, AudioIngestionService
from app.multimodal.errors import AudioValidationError
from app.multimodal.image_processing import ImageEnrichmentService
from app.multimodal.interfaces import OCRProvider, TranscriptionProvider, VisionProvider
from app.multimodal.ocr import NullOCRProvider, TesseractOCRProvider
from app.multimodal.repository import ArtifactRepository
from app.multimodal.transcription import NullTranscriptionProvider, WhisperTranscriptionProvider
from app.multimodal.vision import NullVisionProvider, OllamaVisionProvider
from app.schemas.documents import (
    ArtifactListResponse,
    ArtifactResponse,
    ChunkResponse,
    DocumentListResponse,
    DocumentResponse,
    IngestionResultResponse,
)

router = APIRouter(prefix="/documents", tags=["documents"])
chunks_router = APIRouter(prefix="/chunks", tags=["chunks"])
artifacts_router = APIRouter(prefix="/artifacts", tags=["artifacts"])


def _get_connection(
    settings: Settings = Depends(get_settings),
) -> Generator[sqlite3.Connection, None, None]:
    conn = get_connection(settings.sqlite_path)
    init_db(conn)
    try:
        yield conn
    finally:
        conn.close()


def _audio_extensions(settings: Settings) -> tuple[str, ...]:
    return tuple(ext.strip().lower() for ext in settings.audio_supported_extensions_raw.split(","))


def get_vision_provider(settings: Settings = Depends(get_settings)) -> VisionProvider:
    if settings.vlm_provider == "ollama":
        return OllamaVisionProvider(
            settings.ollama_base_url,
            settings.vlm_model,
            max_tokens=settings.vlm_max_tokens,
            timeout_seconds=settings.vlm_timeout_seconds,
        )
    return NullVisionProvider()


def get_ocr_provider(settings: Settings = Depends(get_settings)) -> OCRProvider:
    if settings.ocr_provider == "tesseract":
        return TesseractOCRProvider()
    return NullOCRProvider()


def get_transcription_provider(settings: Settings = Depends(get_settings)) -> TranscriptionProvider:
    if settings.transcription_provider == "whisper":
        return WhisperTranscriptionProvider(
            settings.whisper_model, settings.whisper_device, settings.whisper_compute_type
        )
    return NullTranscriptionProvider()


def _get_ingestion_service(
    settings: Settings = Depends(get_settings),
    conn: sqlite3.Connection = Depends(_get_connection),
    vision_provider: VisionProvider = Depends(get_vision_provider),
    ocr_provider: OCRProvider = Depends(get_ocr_provider),
) -> IngestionService:
    data_paths = DataPaths(settings.data_dir)
    image_storage = FileImageStorage(data_paths)
    parser = DoclingParser(image_storage=image_storage)
    artifact_repo = ArtifactRepository(conn)
    image_enricher = ImageEnrichmentService(
        vision_provider=vision_provider,
        ocr_provider=ocr_provider,
        artifact_repo=artifact_repo,
        data_paths=data_paths,
        max_image_size_bytes=settings.max_image_artifact_size_mb * 1024 * 1024,
        max_image_pixels=settings.max_image_pixels,
    )
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
        image_enricher=image_enricher,
        artifact_repo=artifact_repo,
    )


def _get_audio_ingestion_service(
    settings: Settings = Depends(get_settings),
    conn: sqlite3.Connection = Depends(_get_connection),
    transcription_provider: TranscriptionProvider = Depends(get_transcription_provider),
) -> AudioIngestionService:
    data_paths = DataPaths(settings.data_dir)
    return AudioIngestionService(
        transcription_provider=transcription_provider,
        document_repo=DocumentRepository(conn),
        chunk_repo=ChunkRepository(conn),
        artifact_repo=ArtifactRepository(conn),
        data_paths=data_paths,
        supported_extensions=_audio_extensions(settings),
        max_upload_size_bytes=settings.max_audio_upload_size_mb * 1024 * 1024,
        chunk_target_tokens=settings.transcript_chunk_target_tokens,
        language=settings.whisper_language or None,
    )


def _audio_result_to_response(result: AudioIngestionResult) -> IngestionResultResponse:
    return IngestionResultResponse(
        document_id=result.document_id,
        filename=result.filename,
        status=result.status,
        page_count=None,
        block_count=result.segment_count,
        chunk_count=result.chunk_count,
        duplicate=result.duplicate,
        error_message=result.error_message,
    )


@router.post("/upload", response_model=IngestionResultResponse)
def upload_document(
    file: UploadFile,
    settings: Settings = Depends(get_settings),
    service: IngestionService = Depends(_get_ingestion_service),
    audio_service: AudioIngestionService = Depends(_get_audio_ingestion_service),
) -> IngestionResultResponse:
    filename = file.filename or "upload"
    data = file.file.read()
    extension = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""

    if extension in _audio_extensions(settings):
        try:
            audio_result = audio_service.ingest(filename, data)
        except AudioValidationError as exc:
            raise HTTPException(status_code=400, detail=exc.message) from exc
        return _audio_result_to_response(audio_result)

    try:
        result = service.ingest(filename, data)
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


def _get_data_paths(settings: Settings = Depends(get_settings)) -> DataPaths:
    return DataPaths(settings.data_dir)


@router.delete("/{document_id}", status_code=204)
def delete_document(
    document_id: str,
    conn: sqlite3.Connection = Depends(_get_connection),
    data_paths: DataPaths = Depends(_get_data_paths),
) -> None:
    """Delete a document, its chunks/artifacts/study items, and its stored
    files (spec section 5: document library needs a delete action; no such
    endpoint existed before Phase 6 — see docs/API.md "Planned")."""
    deleted = DocumentRepository(conn).delete(document_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Document not found.")
    delete_document_files(data_paths, document_id)


@router.get("/{document_id}/artifacts", response_model=ArtifactListResponse)
def list_document_artifacts(
    document_id: str,
    conn: sqlite3.Connection = Depends(_get_connection),
) -> ArtifactListResponse:
    """Phase 4: original visual/audio artifact provenance for one document
    (spec section 25). 404s the same way `GET /documents/{id}` does when
    the document itself doesn't exist, rather than silently returning an
    empty list for both "no document" and "no artifacts"."""
    if DocumentRepository(conn).get_by_id(document_id) is None:
        raise HTTPException(status_code=404, detail="Document not found.")
    artifacts = ArtifactRepository(conn).list_for_document(document_id)
    return ArtifactListResponse(
        artifacts=[
            ArtifactResponse(
                id=a.id,
                document_id=a.document_id,
                chunk_id=a.chunk_id,
                artifact_type=a.artifact_type.value,
                storage_path=a.storage_path,
                mime_type=a.mime_type,
                sha256=a.sha256,
                metadata=a.metadata,
                created_at=a.created_at,
            )
            for a in artifacts
        ]
    )


@chunks_router.get("/{chunk_id}", response_model=ChunkResponse)
def get_chunk(
    chunk_id: str,
    conn: sqlite3.Connection = Depends(_get_connection),
) -> ChunkResponse:
    chunk = ChunkRepository(conn).get_by_id(chunk_id)
    if chunk is None:
        raise HTTPException(status_code=404, detail="Chunk not found.")
    return ChunkResponse(
        id=chunk.id,
        document_id=chunk.document_id,
        parent_id=chunk.parent_id,
        chunk_type=chunk.chunk_type.value,
        content=chunk.content,
        page=chunk.page,
        section=chunk.section,
        heading_path=chunk.heading_path,
        token_count=chunk.token_count,
        image_path=chunk.image_path,
        table_content=chunk.table_content,
        equation_content=chunk.equation_content,
        ocr_text=chunk.ocr_text,
        ocr_status=chunk.ocr_status.value,
        vlm_description=chunk.vlm_description,
        vision_status=chunk.vision_status.value,
        artifact_id=chunk.artifact_id,
        audio_start=chunk.audio_start,
        audio_end=chunk.audio_end,
    )


@artifacts_router.get("/{artifact_id}/file")
def get_artifact_file(
    artifact_id: str,
    conn: sqlite3.Connection = Depends(_get_connection),
    data_paths: DataPaths = Depends(_get_data_paths),
) -> FileResponse:
    """Serve an artifact's original bytes (Phase 6: the multimodal evidence
    UI needs to display images/diagrams, which no endpoint exposed before —
    see docs/API.md "Planned"). `storage_path` is resolved back through
    `DataPaths.resolve_stored_path`, which rejects any path escaping the
    data root, the same discipline every other file path on this API
    follows."""
    artifact = ArtifactRepository(conn).get_by_id(artifact_id)
    if artifact is None:
        raise HTTPException(status_code=404, detail="Artifact not found.")
    try:
        path = data_paths.resolve_stored_path(artifact.storage_path)
    except StorageError as exc:
        raise HTTPException(status_code=404, detail="Artifact file not found.") from exc
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Artifact file not found.")
    return FileResponse(path, media_type=artifact.mime_type or "application/octet-stream")
