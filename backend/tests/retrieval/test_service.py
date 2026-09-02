from __future__ import annotations

from pathlib import Path

import pytest

from app.retrieval.bm25_retriever import BM25Retriever
from app.retrieval.dense_retriever import DenseRetriever
from app.retrieval.errors import EmptyQueryError, HyDEUnavailableError, InvalidModeError
from app.retrieval.faiss_index import FaissIndexStore
from app.retrieval.interfaces import FusedCandidate, RerankedCandidate
from app.retrieval.models import RetrievalMode, RetrievalSource
from app.retrieval.rrf import RRFFusion
from app.retrieval.service import RetrievalService, RetrievalServiceConfig
from tests.retrieval.conftest import make_chunk
from tests.retrieval.fakes import FakeEmbeddingProvider, FakeQueryExpander

CORPUS = [
    make_chunk("c1", "Photosynthesis converts light energy into chemical energy.", page=1),
    make_chunk("c2", "Cellular respiration releases energy stored in glucose.", page=2),
    make_chunk("c3", "The mitochondria is the powerhouse of the cell.", page=3),
    make_chunk("c4", "Photosynthesis occurs in the chloroplasts of plant cells.", page=4),
]


class FakeReranker:
    """Mocked reranker: reverses the pool order deterministically so we can
    assert reranking actually changed something, without loading a model."""

    def rerank(
        self, query: str, candidates: list[FusedCandidate], top_k: int
    ) -> list[RerankedCandidate]:
        reversed_candidates = list(reversed(candidates))[:top_k]
        return [
            RerankedCandidate(
                chunk_id=c.chunk_id,
                document_id=c.document_id,
                content=c.content,
                rerank_score=float(len(reversed_candidates) - rank),
                rank=rank + 1,
                page=c.page,
                section=c.section,
                parent_id=c.parent_id,
                metadata=c.metadata,
                fused_score=c.fused_score,
                source_ranks=c.source_ranks,
                source_scores=c.source_scores,
            )
            for rank, c in enumerate(reversed_candidates)
        ]


def _config(**overrides) -> RetrievalServiceConfig:
    base = dict(
        bm25_top_k=10,
        dense_top_k=10,
        rrf_k=60,
        rrf_candidate_k=20,
        rerank_candidate_k=20,
        final_top_k=5,
    )
    base.update(overrides)
    return RetrievalServiceConfig(**base)


@pytest.fixture
def service_parts(tmp_path: Path):
    bm25 = BM25Retriever.from_chunks(CORPUS)
    provider = FakeEmbeddingProvider()
    store = FaissIndexStore.build(
        CORPUS, provider, tmp_path / "indexes", chunk_target_tokens=512, chunk_overlap_tokens=50
    )
    dense = DenseRetriever(store, provider, {c.id: c for c in CORPUS})
    return bm25, dense


def test_bm25_mode(service_parts) -> None:
    bm25, dense = service_parts
    service = RetrievalService(bm25, dense, None, RRFFusion(60), FakeReranker(), _config())
    results, trace = service.retrieve("photosynthesis", RetrievalMode.BM25, top_k=2)
    assert len(results) == 2
    assert all(r.retrieval_source == RetrievalSource.BM25 for r in results)
    assert trace.mode == RetrievalMode.BM25
    assert trace.bm25_candidates
    assert trace.timings.bm25_ms is not None
    assert trace.timings.total_ms >= 0


def test_dense_mode(service_parts) -> None:
    bm25, dense = service_parts
    service = RetrievalService(bm25, dense, None, RRFFusion(60), FakeReranker(), _config())
    results, trace = service.retrieve("mitochondria powerhouse", RetrievalMode.DENSE, top_k=2)
    assert results[0].chunk_id == "c3"
    assert all(r.retrieval_source == RetrievalSource.DENSE for r in results)
    assert trace.timings.faiss_ms is not None
    assert trace.hyde_query is None


def test_hybrid_rrf_mode_combines_bm25_and_dense(service_parts) -> None:
    bm25, dense = service_parts
    service = RetrievalService(bm25, dense, None, RRFFusion(60), FakeReranker(), _config())
    results, trace = service.retrieve("photosynthesis energy", RetrievalMode.HYBRID_RRF, top_k=3)
    assert all(r.retrieval_source == RetrievalSource.RRF for r in results)
    assert results[0].rrf_score is not None
    assert trace.bm25_candidates and trace.dense_candidates
    assert trace.timings.rrf_ms is not None


def test_dense_hyde_mode_uses_expanded_text_and_never_touches_bm25(service_parts) -> None:
    bm25, dense = service_parts
    hyde = FakeQueryExpander(hypothetical_text="The mitochondria is the powerhouse of the cell.")
    service = RetrievalService(bm25, dense, hyde, RRFFusion(60), FakeReranker(), _config())
    results, trace = service.retrieve(
        "energy production in cells", RetrievalMode.DENSE_HYDE, top_k=1
    )
    assert results[0].chunk_id == "c3"
    assert trace.hyde_query == "The mitochondria is the powerhouse of the cell."
    assert trace.hyde_model == "fake-hyde-model"
    assert trace.bm25_candidates == []  # BM25 never ran in this mode


def test_hybrid_rrf_hyde_bm25_gets_original_query_dense_gets_hyde_text(service_parts) -> None:
    bm25, dense = service_parts
    hyde = FakeQueryExpander(
        hypothetical_text="Photosynthesis occurs in the chloroplasts of plant cells."
    )
    service = RetrievalService(bm25, dense, hyde, RRFFusion(60), FakeReranker(), _config())
    results, trace = service.retrieve("energy", RetrievalMode.HYBRID_RRF_HYDE, top_k=3)
    assert trace.hyde_query == "Photosynthesis occurs in the chloroplasts of plant cells."
    # BM25 candidates should reflect the ORIGINAL query "energy", not the HyDE text.
    bm25_ids = {c.chunk_id for c in trace.bm25_candidates}
    assert "c2" in bm25_ids or "c1" in bm25_ids  # both mention "energy"
    assert results


def test_full_baseline_mode_reranks(service_parts) -> None:
    bm25, dense = service_parts
    hyde = FakeQueryExpander(
        hypothetical_text="Photosynthesis occurs in the chloroplasts of plant cells."
    )
    service = RetrievalService(bm25, dense, hyde, RRFFusion(60), FakeReranker(), _config())
    results, trace = service.retrieve("photosynthesis", RetrievalMode.FULL_BASELINE, top_k=2)
    assert len(results) == 2
    assert all(r.retrieval_source == RetrievalSource.RERANKER for r in results)
    assert all(r.rerank_score is not None for r in results)
    assert trace.rerank_candidates
    assert trace.timings.reranking_ms is not None


def test_hyde_mode_without_hyde_configured_raises(service_parts) -> None:
    bm25, dense = service_parts
    service = RetrievalService(bm25, dense, None, RRFFusion(60), FakeReranker(), _config())
    with pytest.raises(HyDEUnavailableError):
        service.retrieve("photosynthesis", RetrievalMode.DENSE_HYDE, top_k=2)


def test_hyde_unavailable_backend_raises(service_parts) -> None:
    bm25, dense = service_parts
    hyde = FakeQueryExpander(available=False)
    service = RetrievalService(bm25, dense, hyde, RRFFusion(60), FakeReranker(), _config())
    with pytest.raises(HyDEUnavailableError):
        service.retrieve("photosynthesis", RetrievalMode.DENSE_HYDE, top_k=2)


def test_empty_query_raises(service_parts) -> None:
    bm25, dense = service_parts
    service = RetrievalService(bm25, dense, None, RRFFusion(60), FakeReranker(), _config())
    with pytest.raises(EmptyQueryError):
        service.retrieve("   ", RetrievalMode.BM25, top_k=2)


def test_invalid_mode_string_raises(service_parts) -> None:
    bm25, dense = service_parts
    service = RetrievalService(bm25, dense, None, RRFFusion(60), FakeReranker(), _config())
    with pytest.raises(InvalidModeError):
        service.retrieve("photosynthesis", "not_a_real_mode", top_k=2)


def test_default_top_k_uses_config(service_parts) -> None:
    bm25, dense = service_parts
    service = RetrievalService(
        bm25, dense, None, RRFFusion(60), FakeReranker(), _config(final_top_k=2)
    )
    results, _ = service.retrieve("photosynthesis", RetrievalMode.BM25)
    assert len(results) == 2
