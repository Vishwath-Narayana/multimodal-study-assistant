"""Chunk-eligibility rule shared by every text index (BM25 and dense/FAISS).

**Document filtering rule** (Phase 2 spec, "only index chunks that make
sense for textual retrieval"; extended in Phase 4):

- Every chunk type is indexed **if and only if its `content` field is
  non-empty after stripping whitespace**. In practice:
  - Table chunks: Phase 1 chunking always populates `content` with a
    pipe/semicolon text rendering of `table_content` (see
    docs/architecture/ingestion.md §8), so table chunks are indexed.
  - Equation chunks: indexed only when `equation_content`/`content` is
    non-empty. Phase 1 currently does not classify parsed equations as
    `EQUATION` blocks (formula enrichment is disabled — see
    docs/architecture/ingestion.md §4 "Known limitations"), so in practice
    no chunk has this type yet; the rule is still implemented so equation
    chunks are indexed correctly once that changes.
  - Caption/code/unknown/heading/paragraph/list/transcript chunks: indexed
    whenever they carry non-empty text, same rule.
  - **Image chunks** (Phase 2, unchanged through Phase 3): a `BlockType.
    IMAGE` chunk with no textual representation had empty `content`, so it
    was excluded by the general non-empty rule above — Phase 1/2/3 added an
    explicit `IMAGE` exclusion on top of that for clarity/documentation
    purposes only. **Phase 4 removes that explicit exclusion**: once
    `app.multimodal.image_processing.ImageEnrichmentService` runs, an image
    chunk's `content` holds the combined VLM description + OCR text +
    surrounding context (LEVEL 1 textual representation — see
    docs/architecture/multimodal.md "Visual Embeddings"), so it is now
    eligible under the same non-empty-content rule everything else already
    uses. An unenriched image chunk (no VLM/OCR configured) still has empty
    `content` and is still excluded — behavior for that case is unchanged.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from app.ingestion.models import Chunk, VisionStatus


def is_eligible_for_text_index(chunk: Chunk) -> bool:
    return bool(chunk.content and chunk.content.strip())


def eligible_chunks(chunks: Iterable[Chunk]) -> list[Chunk]:
    return [c for c in chunks if is_eligible_for_text_index(c)]


def chunk_metadata(chunk: Chunk) -> dict[str, Any]:
    """The `RetrievalCandidate.metadata` dict built for one chunk.

    Shared by `BM25Retriever`/`DenseRetriever` so both sources attach the
    same multimodal fields the same way (spec section 20: "Phase 3's
    grounded generation must be able to receive multimodal evidence
    metadata") — populated only when the chunk actually carries that field,
    so a plain text chunk's metadata stays small. This dict survives RRF
    fusion and reranking unchanged (`FusedCandidate`/`RerankedCandidate`
    both pass `metadata` through as-is), so it reaches
    `RetrievalResult.metadata` — and from there the `/chat/query` response
    and citation validation — without any change needed in those layers.
    """
    metadata: dict[str, Any] = {"chunk_type": chunk.chunk_type.value}
    if chunk.ocr_text:
        metadata["ocr_text"] = chunk.ocr_text
    if chunk.vlm_description:
        metadata["vlm_description"] = chunk.vlm_description
    if chunk.vision_status != VisionStatus.NOT_ATTEMPTED:
        metadata["vision_status"] = chunk.vision_status.value
    if chunk.image_path:
        metadata["original_artifact"] = chunk.image_path
    if chunk.table_content:
        metadata["table_content"] = chunk.table_content
    if chunk.audio_start is not None:
        metadata["audio_start"] = chunk.audio_start
    if chunk.audio_end is not None:
        metadata["audio_end"] = chunk.audio_end
    return metadata
