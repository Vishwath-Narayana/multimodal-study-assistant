"""Dense (embedding + FAISS) retrieval.

`DenseRetriever` is the `Retriever` adapter around `FaissIndexStore` +
`EmbeddingProvider` — downstream code depends on this class, never on
`faiss`/`sentence_transformers` directly (ADR-004-style separation).

Runnable independently of HyDE: `retrieve(query, top_k)` always embeds
whatever string it is given. `HybridRetriever` decides whether that string
is the original query or HyDE-generated text — this class has no opinion.
"""

from __future__ import annotations

from app.ingestion.models import Chunk
from app.retrieval.corpus import chunk_metadata
from app.retrieval.embeddings import EmbeddingProvider
from app.retrieval.errors import EmptyQueryError
from app.retrieval.faiss_index import FaissIndexStore
from app.retrieval.interfaces import Retriever
from app.retrieval.models import RetrievalCandidate


class DenseRetriever(Retriever):
    def __init__(
        self,
        index_store: FaissIndexStore,
        embedding_provider: EmbeddingProvider,
        chunks_by_id: dict[str, Chunk],
    ) -> None:
        self._index_store = index_store
        self._embedding_provider = embedding_provider
        self._chunks_by_id = chunks_by_id

    def retrieve(self, query: str, top_k: int) -> list[RetrievalCandidate]:
        if not query or not query.strip():
            raise EmptyQueryError("Dense retrieval query must not be empty.")
        if top_k <= 0:
            return []

        query_vector = self._embedding_provider.embed_query(query)
        hits = self._index_store.search(query_vector, top_k)

        results: list[RetrievalCandidate] = []
        for rank, (chunk_id, score) in enumerate(hits, start=1):
            chunk = self._chunks_by_id.get(chunk_id)
            if chunk is None:
                # Id map points at a chunk that's no longer available in the
                # current lookup (e.g. deleted since the index was built) —
                # skip rather than fabricate a result. StaleIndexError
                # checks (via FaissIndexStore.raise_if_stale) are the
                # primary guard against this; this is a defensive fallback.
                continue
            results.append(
                RetrievalCandidate(
                    chunk_id=chunk.id,
                    document_id=chunk.document_id,
                    content=chunk.content,
                    rank=rank,
                    score=score,
                    page=chunk.page,
                    section=chunk.section,
                    parent_id=chunk.parent_id,
                    metadata=chunk_metadata(chunk),
                )
            )
        return results
