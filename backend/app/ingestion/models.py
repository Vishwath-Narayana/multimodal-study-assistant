"""Canonical internal document model.

This module is the stable domain representation the rest of the application
depends on. It is intentionally independent of Docling's internal classes
(``docling_core.types.doc.*``) so that a future parser swap does not ripple
through chunking, persistence, or the API layer — see
docs/decisions/ADR-004-model-agnostic-interfaces.md.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum


class BlockType(StrEnum):
    """The kinds of structural content a parser can produce.

    Content is only ever classified as one of these when the parser is
    confident about it; anything else is UNKNOWN rather than forced into an
    incorrect type.

    ``TRANSCRIPT`` is a Phase 4 addition for audio-derived chunks (see
    :mod:`app.multimodal.audio_chunking`) — there is no Docling equivalent,
    since audio never goes through the document parser. Phase 4 does not
    add a separate ``DIAGRAM`` type: Docling's ``PICTURE`` label does not
    distinguish photos from diagrams, so both are represented as ``IMAGE``
    (documented in docs/architecture/multimodal.md rather than fabricating
    a distinction the parser cannot actually make).
    """

    HEADING = "heading"
    PARAGRAPH = "paragraph"
    LIST = "list"
    TABLE = "table"
    IMAGE = "image"
    EQUATION = "equation"
    CODE = "code"
    CAPTION = "caption"
    TRANSCRIPT = "transcript"
    UNKNOWN = "unknown"


class VisionStatus(StrEnum):
    """Whether VLM/OCR-derived analysis of a visual artifact actually ran.

    Kept as an explicit closed set rather than a bool so downstream code
    (and the API response) can distinguish "no VLM configured" from "VLM
    configured but this call failed" from "successfully described" —
    spec: "Never claim a VLM description exists when it was not
    generated." Reused for OCR status too (see
    ``DocumentBlock.ocr_status``) rather than introducing a near-identical
    second enum.
    """

    NOT_ATTEMPTED = "not_attempted"
    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"
    FAILED = "failed"


@dataclass
class DocumentMetadata:
    """Document-level metadata, extracted where the source format provides it."""

    title: str | None = None
    author: str | None = None
    subject: str | None = None
    created_at: datetime | None = None
    modified_at: datetime | None = None
    page_count: int | None = None
    source_filename: str = ""
    file_hash: str = ""


@dataclass
class DocumentBlock:
    """A single structural unit extracted from a source document.

    ``heading_path`` carries the chain of ancestor headings (e.g.
    ``["Chapter 1", "Section 1.1"]``) so that downstream chunking and
    citations can reconstruct where in the document this content lives
    without re-parsing the source.
    """

    id: str
    type: BlockType
    content: str
    order: int
    page: int | None = None
    section: str | None = None
    heading_path: list[str] = field(default_factory=list)
    parent_block_id: str | None = None

    # Multimodal payloads. Populated only when the block's type matches;
    # left as None otherwise. Phase 1 preserved this data without
    # interpreting it (no VLM captions, no OCR pipeline, no table QA) —
    # Phase 4 adds the interpretation below while keeping the original
    # artifact fields (image_path, table_content, equation_content)
    # untouched, per docs/architecture/multimodal.md "original evidence
    # must be preserved, not replaced by derived text".
    image_path: str | None = None
    table_content: list[list[str]] | None = None
    equation_content: str | None = None

    # --- Phase 4: derived multimodal analysis, additive to the fields above ---
    ocr_text: str | None = None
    ocr_status: VisionStatus = VisionStatus.NOT_ATTEMPTED
    vlm_description: str | None = None
    vision_status: VisionStatus = VisionStatus.NOT_ATTEMPTED
    artifact_id: str | None = None

    # --- Phase 4: audio/transcript-only fields ---
    audio_start: float | None = None
    audio_end: float | None = None

    metadata: dict[str, str] = field(default_factory=dict)


@dataclass
class ParsedDocument:
    """The canonical output of any :class:`~app.ingestion.parsers.base.DocumentParser`."""

    id: str
    filename: str
    file_hash: str
    file_type: str
    metadata: DocumentMetadata
    blocks: list[DocumentBlock] = field(default_factory=list)


@dataclass
class Chunk:
    """A retrieval-ready unit produced by structure-aware chunking.

    ``parent_id`` links a text/table/image/equation chunk to its enclosing
    section chunk (see :mod:`app.ingestion.chunking`). This is only a data
    representation in Phase 1 — no retrieval logic reads ``parent_id`` yet.
    """

    id: str
    document_id: str
    order: int
    chunk_type: BlockType
    content: str
    parent_id: str | None = None
    page: int | None = None
    section: str | None = None
    heading_path: list[str] = field(default_factory=list)
    token_count: int = 0

    image_path: str | None = None
    table_content: list[list[str]] | None = None
    equation_content: str | None = None

    # --- Phase 4: derived multimodal analysis (see DocumentBlock docstring) ---
    ocr_text: str | None = None
    ocr_status: VisionStatus = VisionStatus.NOT_ATTEMPTED
    vlm_description: str | None = None
    vision_status: VisionStatus = VisionStatus.NOT_ATTEMPTED
    artifact_id: str | None = None
    audio_start: float | None = None
    audio_end: float | None = None
