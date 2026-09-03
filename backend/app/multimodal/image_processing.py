"""Image/diagram enrichment orchestration (spec sections 6-9).

`ImageEnrichmentService` composes OCR + VLM description over one already-
extracted image block (Phase 1's `DoclingParser` already saved the pixels
via `FileImageStorage` — this module never re-extracts images itself, only
enriches what Phase 1 produced), and builds the combined searchable text
that lets an image chunk participate in the existing BM25/FAISS pipeline
(spec section 17, LEVEL 1: textual representation, not a direct visual
embedding — see docs/architecture/multimodal.md "Visual Embeddings").

Original visual evidence is always preserved regardless of OCR/VLM outcome
(spec section 7): `block.image_path` is untouched, `ocr_text`/
`vlm_description` are stored on their own fields (never overwriting each
other), and `content` becomes a *derived* combination of them plus
surrounding context — never a replacement for the original image.
"""

from __future__ import annotations

from app.ingestion.hashing import sha256_bytes
from app.ingestion.models import DocumentBlock, VisionStatus
from app.ingestion.storage import DataPaths
from app.multimodal.interfaces import OCRProvider, VisionProvider
from app.multimodal.models import Artifact, ArtifactType
from app.multimodal.repository import ArtifactRepository
from app.multimodal.security import validate_image_artifact


class ImageEnrichmentService:
    def __init__(
        self,
        *,
        vision_provider: VisionProvider,
        ocr_provider: OCRProvider,
        artifact_repo: ArtifactRepository,
        data_paths: DataPaths,
        max_image_size_bytes: int,
        max_image_pixels: int,
    ) -> None:
        self._vision = vision_provider
        self._ocr = ocr_provider
        self._artifacts = artifact_repo
        self._paths = data_paths
        self._max_image_size_bytes = max_image_size_bytes
        self._max_image_pixels = max_image_pixels

    def enrich(self, document_id: str, block: DocumentBlock) -> DocumentBlock:
        """Returns a new `DocumentBlock` with OCR/VLM fields, `artifact_id`,
        and a combined `content` populated. Leaves `block` itself
        unmodified (dataclasses.replace-style, matching the rest of the
        ingestion pipeline's preference for pure transformations)."""
        if block.image_path is None:
            return block

        absolute_path = self._paths.root / block.image_path
        try:
            validate_image_artifact(
                absolute_path,
                max_size_bytes=self._max_image_size_bytes,
                max_pixels=self._max_image_pixels,
            )
        except Exception:
            # An artifact that fails validation is not enriched, but the
            # original image reference is still preserved (spec section 7)
            # — the block is returned with vision/ocr left NOT_ATTEMPTED
            # rather than the whole document failing.
            return block

        ocr_result = self._ocr.extract(absolute_path)
        vision_result = self._vision.describe(absolute_path, context=block.section or "")

        artifact_id = f"{document_id}::artifact::{block.id}"
        try:
            sha256 = sha256_bytes(absolute_path.read_bytes())
        except OSError:
            sha256 = None
        self._artifacts.create(
            Artifact(
                id=artifact_id,
                document_id=document_id,
                artifact_type=ArtifactType.IMAGE,
                storage_path=block.image_path,
                mime_type="image/png",
                sha256=sha256,
                metadata={
                    "page": block.page,
                    "section": block.section,
                    "ocr_status": ocr_result.status.value,
                    "vision_status": vision_result.status.value,
                },
            )
        )

        content = _build_searchable_text(
            vlm_description=vision_result.description,
            ocr_text=ocr_result.text,
            surrounding_text=block.section,
        )

        return DocumentBlock(
            id=block.id,
            type=block.type,
            content=content,
            order=block.order,
            page=block.page,
            section=block.section,
            heading_path=list(block.heading_path),
            parent_block_id=block.parent_block_id,
            image_path=block.image_path,
            table_content=block.table_content,
            equation_content=block.equation_content,
            ocr_text=ocr_result.text,
            ocr_status=ocr_result.status,
            vlm_description=vision_result.description,
            vision_status=vision_result.status,
            artifact_id=artifact_id,
            audio_start=block.audio_start,
            audio_end=block.audio_end,
            metadata=dict(block.metadata),
        )


def _build_searchable_text(
    *, vlm_description: str | None, ocr_text: str | None, surrounding_text: str | None
) -> str:
    """spec section 17: `searchable_text = VLM description + OCR + surrounding text`."""
    parts = [p for p in (vlm_description, ocr_text, surrounding_text) if p and p.strip()]
    return "\n".join(parts)


def unavailable_status(*, vision_status: VisionStatus) -> bool:
    """True when a status means "no analysis was actually produced" —
    small helper kept here (rather than inlined at each call site) since
    both API responses and evaluation code need the same definition of
    "usable"."""
    return vision_status in (
        VisionStatus.UNAVAILABLE,
        VisionStatus.FAILED,
        VisionStatus.NOT_ATTEMPTED,
    )
