from __future__ import annotations

from pathlib import Path

import pytest

from app.retrieval.bm25_retriever import BM25Retriever
from app.retrieval.dense_retriever import DenseRetriever
from app.retrieval.faiss_index import FaissIndexStore
from app.retrieval.hybrid import HybridRetriever, inspect_union
from app.retrieval.rrf import RRFFusion
from tests.retrieval.conftest import make_chunk
from tests.retrieval.fakes import FakeEmbeddingProvider

CORPUS = [
    make_chunk("c1", "Photosynthesis converts light energy into chemical energy."),
    make_chunk("c2", "Cellular respiration releases energy stored in glucose."),
    make_chunk("c3", "The mitochondria is the powerhouse of the cell."),
]


@pytest.fixture
def hybrid(tmp_path: Path) -> HybridRetriever:
    bm25 = BM25Retriever.from_chunks(CORPUS)
    provider = FakeEmbeddingProvider()
    store = FaissIndexStore.build(
        CORPUS, provider, tmp_path / "indexes", chunk_target_tokens=512, chunk_overlap_tokens=50
    )
    dense = DenseRetriever(store, provider, {c.id: c for c in CORPUS})
    return HybridRetriever(bm25, dense, RRFFusion(k=60))


def test_retrieve_returns_bm25_dense_and_fused(hybrid: HybridRetriever) -> None:
    output = hybrid.retrieve("energy", "energy", bm25_top_k=5, dense_top_k=5)
    assert output.bm25_candidates
    assert output.dense_candidates
    assert output.fused_candidates
    assert all(c.rank >= 1 for c in output.fused_candidates)


def test_bm25_and_dense_queries_can_differ(hybrid: HybridRetriever) -> None:
    # Simulates the HyDE path: bm25 gets the original query, dense gets a
    # different (expanded) string.
    output = hybrid.retrieve(
        bm25_query="mitochondria",
        dense_query="The mitochondria is the powerhouse of the cell.",
        bm25_top_k=5,
        dense_top_k=5,
    )
    assert output.bm25_candidates[0].chunk_id == "c3"
    assert output.dense_candidates[0].chunk_id == "c3"


def test_inspect_union_dedupes_and_preserves_order() -> None:
    bm25_list = [
        _make_candidate("a"),
        _make_candidate("b"),
    ]
    dense_list = [
        _make_candidate("b"),
        _make_candidate("c"),
    ]
    union = inspect_union(bm25_list, dense_list)
    assert [c.chunk_id for c in union] == ["a", "b", "c"]


def _make_candidate(chunk_id: str):
    from app.retrieval.models import RetrievalCandidate

    return RetrievalCandidate(
        chunk_id=chunk_id, document_id="doc-1", content="x", rank=1, score=1.0
    )
