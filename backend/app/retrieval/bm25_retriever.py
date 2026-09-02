"""BM25 lexical retrieval, backed by the `rank-bm25` library.

BM25 always scores the **original user query** — it must never receive HyDE
text (see `docs/architecture/retrieval.md`). Enforced structurally: this
class's `retrieve()` takes whatever string it is given and has no notion of
HyDE at all; routing the original query to it is `HybridRetriever`'s job.
"""

from __future__ import annotations

from dataclasses import dataclass

from rank_bm25 import BM25Okapi

from app.ingestion.models import Chunk
from app.retrieval.corpus import eligible_chunks
from app.retrieval.errors import NoIndexedChunksError
from app.retrieval.interfaces import Retriever
from app.retrieval.models import RetrievalCandidate
from app.retrieval.tokenizer import tokenize


@dataclass
class _IndexedChunk:
    chunk: Chunk
    tokens: list[str]


class BM25Retriever(Retriever):
    """In-memory BM25Okapi index over eligible chunks.

    Rebuilt explicitly via `from_chunks`/`rebuild` — no hidden mutation, no
    implicit reload on every query. Indexing is deterministic: the same
    chunk set always produces the same term statistics and the same
    chunk-id ordering (chunks are indexed in the order given, which
    `ChunkRepository.list_all()` returns deterministically).
    """

    def __init__(self, indexed_chunks: list[_IndexedChunk]) -> None:
        self._indexed = indexed_chunks
        self._chunk_ids = [ic.chunk.id for ic in indexed_chunks]
        if indexed_chunks:
            self._bm25 = BM25Okapi([ic.tokens for ic in indexed_chunks])
        else:
            self._bm25 = None

    @classmethod
    def from_chunks(cls, chunks: list[Chunk]) -> "BM25Retriever":
        """Build a fresh index. Raises `NoIndexedChunksError` if, after
        applying the text-eligibility filter (`app.retrieval.corpus`),
        nothing is left to index."""
        eligible = eligible_chunks(chunks)
        if not eligible:
            raise NoIndexedChunksError(
                "No text-eligible chunks are available to build a BM25 index."
            )
        # Deterministic chunk-id de-duplication: a chunk id should never
        # appear twice (Phase 1 SHA-256-dedupes documents, and
        # `ChunkRepository.replace_for_document` deletes-then-inserts per
        # document), but we guard against it explicitly here rather than
        # silently indexing a duplicate twice.
        seen: set[str] = set()
        deduped: list[Chunk] = []
        for chunk in eligible:
            if chunk.id in seen:
                continue
            seen.add(chunk.id)
            deduped.append(chunk)
        indexed = [_IndexedChunk(chunk=c, tokens=tokenize(c.content)) for c in deduped]
        return cls(indexed)

    def rebuild(self, chunks: list[Chunk]) -> "BM25Retriever":
        return BM25Retriever.from_chunks(chunks)

    @property
    def size(self) -> int:
        return len(self._indexed)

    def retrieve(self, query: str, top_k: int) -> list[RetrievalCandidate]:
        if self._bm25 is None or not self._indexed:
            raise NoIndexedChunksError("BM25 index has no chunks to search.")
        if top_k <= 0:
            return []
        query_tokens = tokenize(query)
        if not query_tokens:
            # Empty/unmatchable query: BM25 has no lexical signal at all —
            # return no candidates rather than an arbitrary/undefined order.
            return []

        scores = self._bm25.get_scores(query_tokens)
        # Deterministic tie-breaking: sort by (-score, chunk_id) so equal
        # scores always resolve the same way regardless of dict/array
        # iteration order.
        ranked = sorted(
            range(len(self._indexed)),
            key=lambda i: (-scores[i], self._chunk_ids[i]),
        )[:top_k]

        results: list[RetrievalCandidate] = []
        for rank, idx in enumerate(ranked, start=1):
            chunk = self._indexed[idx].chunk
            results.append(
                RetrievalCandidate(
                    chunk_id=chunk.id,
                    document_id=chunk.document_id,
                    content=chunk.content,
                    rank=rank,
                    score=float(scores[idx]),
                    page=chunk.page,
                    section=chunk.section,
                    parent_id=chunk.parent_id,
                    metadata={"chunk_type": chunk.chunk_type.value},
                )
            )
        return results
