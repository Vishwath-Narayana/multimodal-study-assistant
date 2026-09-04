from __future__ import annotations

from pathlib import Path

import pytest

from app.retrieval.dense_retriever import DenseRetriever
from app.retrieval.errors import EmptyQueryError
from app.retrieval.faiss_index import FaissIndexStore
from tests.retrieval.conftest import make_chunk
from tests.retrieval.fakes import FakeEmbeddingProvider

CORPUS = [
    make_chunk("c1", "Photosynthesis converts light energy into chemical energy.", page=1),
    make_chunk("c2", "Cellular respiration releases energy stored in glucose.", page=2),
    make_chunk("c3", "The mitochondria is the powerhouse of the cell.", page=3),
]


@pytest.fixture
def dense_retriever(tmp_path: Path) -> DenseRetriever:
    provider = FakeEmbeddingProvider()
    store = FaissIndexStore.build(
        CORPUS, provider, tmp_path / "indexes", chunk_target_tokens=512, chunk_overlap_tokens=50
    )
    return DenseRetriever(store, provider, {c.id: c for c in CORPUS})


def test_retrieve_returns_ranked_candidates(dense_retriever: DenseRetriever) -> None:
    results = dense_retriever.retrieve(CORPUS[0].content, top_k=3)
    assert results[0].chunk_id == "c1"
    assert results[0].rank == 1
    assert all(r.rank == i + 1 for i, r in enumerate(results))


def test_metadata_preserved(dense_retriever: DenseRetriever) -> None:
    results = dense_retriever.retrieve(CORPUS[2].content, top_k=1)
    assert results[0].page == 3
    assert results[0].document_id == "doc-1"


def test_top_k_respected(dense_retriever: DenseRetriever) -> None:
    results = dense_retriever.retrieve("energy", top_k=2)
    assert len(results) == 2


def test_empty_query_raises(dense_retriever: DenseRetriever) -> None:
    with pytest.raises(EmptyQueryError):
        dense_retriever.retrieve("", top_k=5)


def test_independently_runnable_without_hyde(dense_retriever: DenseRetriever) -> None:
    # No HyDE component is constructed/used anywhere in this test — dense
    # retrieval works standalone on the original query text.
    results = dense_retriever.retrieve("mitochondria powerhouse", top_k=1)
    assert results[0].chunk_id == "c3"
