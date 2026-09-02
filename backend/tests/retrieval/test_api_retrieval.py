from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.api import retrieval as retrieval_api
from app.main import create_app
from app.retrieval.bm25_retriever import BM25Retriever
from app.retrieval.dense_retriever import DenseRetriever
from app.retrieval.faiss_index import FaissIndexStore
from app.retrieval.reranker import CrossEncoderReranker
from tests.retrieval.conftest import make_chunk
from tests.retrieval.fakes import FakeEmbeddingProvider

CORPUS = [
    make_chunk("c1", "Photosynthesis converts light energy into chemical energy.", page=1),
    make_chunk("c2", "Cellular respiration releases energy stored in glucose.", page=2),
]


class _FakeCrossEncoder:
    def predict(self, pairs):
        return [1.0 for _ in pairs]


@pytest.fixture
def client(tmp_path: Path) -> TestClient:
    app = create_app()

    bm25 = BM25Retriever.from_chunks(CORPUS)
    provider = FakeEmbeddingProvider()
    store = FaissIndexStore.build(
        CORPUS, provider, tmp_path / "indexes", chunk_target_tokens=512, chunk_overlap_tokens=50
    )
    dense = DenseRetriever(store, provider, {c.id: c for c in CORPUS})
    reranker = CrossEncoderReranker("fake")
    reranker._model = _FakeCrossEncoder()

    app.dependency_overrides[retrieval_api.get_bm25_retriever] = lambda: bm25
    app.dependency_overrides[retrieval_api.get_dense_retriever] = lambda: dense
    app.dependency_overrides[retrieval_api.get_hyde_expander] = lambda: None
    app.dependency_overrides[retrieval_api.get_reranker] = lambda: reranker
    return TestClient(app)


def test_search_bm25_mode(client: TestClient) -> None:
    response = client.post(
        "/retrieval/search", json={"query": "photosynthesis", "mode": "bm25", "top_k": 2}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["mode"] == "bm25"
    assert body["results"][0]["chunk_id"] == "c1"
    assert body["results"][0]["retrieval_source"] == "bm25"
    assert "content_preview" in body["results"][0]
    assert body["timing"]["total_ms"] >= 0


def test_search_hybrid_rrf_mode(client: TestClient) -> None:
    response = client.post(
        "/retrieval/search", json={"query": "energy", "mode": "hybrid_rrf", "top_k": 2}
    )
    assert response.status_code == 200
    body = response.json()
    assert all(r["retrieval_source"] == "rrf" for r in body["results"])


def test_search_invalid_mode_returns_400(client: TestClient) -> None:
    response = client.post(
        "/retrieval/search", json={"query": "energy", "mode": "not_a_mode", "top_k": 2}
    )
    assert response.status_code == 400


def test_search_empty_query_returns_400(client: TestClient) -> None:
    response = client.post("/retrieval/search", json={"query": "  ", "mode": "bm25", "top_k": 2})
    assert response.status_code == 400


def test_search_hyde_mode_without_hyde_configured_returns_503(client: TestClient) -> None:
    response = client.post(
        "/retrieval/search", json={"query": "energy", "mode": "dense_hyde", "top_k": 2}
    )
    assert response.status_code == 503


def test_search_full_baseline_mode(client: TestClient) -> None:
    response = client.post(
        "/retrieval/search", json={"query": "photosynthesis", "mode": "full_baseline", "top_k": 1}
    )
    assert response.status_code == 503  # HyDE not configured in this fixture -> explicit error
