"""Chunk-eligibility rule shared by every text index (BM25 and dense/FAISS).

**Document filtering rule** (Phase 2 spec, "only index chunks that make
sense for textual retrieval"):

- `BlockType.IMAGE` chunks are excluded from text retrieval — Phase 1 does
  not produce any textual representation of image content (no VLM
  captioning yet, see docs/architecture/ingestion.md), so there is nothing
  meaningful for BM25/dense embeddings to match against. The chunk row
  itself is left untouched in SQLite for later multimodal phases — this
  module only filters what gets *indexed*, it never deletes anything.
- Every other chunk type is indexed **if and only if its `content` field is
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
  - Caption/code/unknown/heading/paragraph/list chunks: indexed whenever
    they carry non-empty text, same rule.
"""

from __future__ import annotations

from collections.abc import Iterable

from app.ingestion.models import BlockType, Chunk

_EXCLUDED_TYPES = frozenset({BlockType.IMAGE})


def is_eligible_for_text_index(chunk: Chunk) -> bool:
    if chunk.chunk_type in _EXCLUDED_TYPES:
        return False
    return bool(chunk.content and chunk.content.strip())


def eligible_chunks(chunks: Iterable[Chunk]) -> list[Chunk]:
    return [c for c in chunks if is_eligible_for_text_index(c)]
