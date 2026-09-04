from typing import Any

from pydantic import BaseModel


class DocumentResponse(BaseModel):
    id: str
    filename: str
    file_type: str
    file_hash: str
    status: str
    uploaded_at: str
    updated_at: str
    page_count: int | None = None
    title: str | None = None
    author: str | None = None
    subject: str | None = None
    block_count: int | None = None
    chunk_count: int | None = None
    error_message: str | None = None


class DocumentListResponse(BaseModel):
    documents: list[DocumentResponse]


class IngestionResultResponse(BaseModel):
    document_id: str
    filename: str
    status: str
    page_count: int | None = None
    block_count: int
    chunk_count: int
    duplicate: bool
    error_message: str | None = None


class ArtifactResponse(BaseModel):
    """Phase 4: one preserved original visual/audio artifact — see
    docs/architecture/multimodal.md "Provenance". `storage_path` is a path
    relative to the data root (never absolute, never exposed as a direct
    filesystem path), same convention as `chunk.image_path`."""

    id: str
    document_id: str
    chunk_id: str | None = None
    artifact_type: str
    storage_path: str
    mime_type: str | None = None
    sha256: str | None = None
    metadata: dict[str, Any] = {}
    created_at: str


class ArtifactListResponse(BaseModel):
    artifacts: list[ArtifactResponse]


class ChunkResponse(BaseModel):
    """Phase 4: `GET /chunks/{id}` — a single chunk's full stored
    representation, including multimodal fields, for debugging/
    explainability (spec section 25). Unlike `content_preview` elsewhere,
    this returns full `content` — it is a research/debug endpoint, not
    part of the citation-safe response surface (see
    docs/research/security.md)."""

    id: str
    document_id: str
    parent_id: str | None = None
    chunk_type: str
    content: str
    page: int | None = None
    section: str | None = None
    heading_path: list[str]
    token_count: int
    image_path: str | None = None
    table_content: list[list[str]] | None = None
    equation_content: str | None = None
    ocr_text: str | None = None
    ocr_status: str
    vlm_description: str | None = None
    vision_status: str
    artifact_id: str | None = None
    audio_start: float | None = None
    audio_end: float | None = None
