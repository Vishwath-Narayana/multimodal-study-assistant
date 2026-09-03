from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.api import chat as chat_api
from app.api import retrieval as retrieval_api
from app.core.config import get_settings
from app.ingestion.repository import DocumentRepository, DocumentUpsert, get_connection
from app.main import create_app
from app.retrieval.bm25_retriever import BM25Retriever
from app.retrieval.dense_retriever import DenseRetriever
from app.retrieval.faiss_index import FaissIndexStore
from tests.generation.fakes import FakeGenerator
from tests.retrieval.conftest import make_chunk
from tests.retrieval.fakes import FakeEmbeddingProvider

CORPUS = [
    make_chunk("c1", "Photosynthesis converts light energy into chemical energy.", page=1),
    make_chunk("c2", "Cellular respiration releases energy stored in glucose.", page=2),
]


class _FakeReranker:
    def rerank(self, query, candidates, top_k):  # type: ignore[no-untyped-def]
        from app.retrieval.interfaces import RerankedCandidate

        return [
            RerankedCandidate(
                chunk_id=c.chunk_id,
                document_id=c.document_id,
                content=c.content,
                rerank_score=2.0,
                rank=rank + 1,
                page=c.page,
                section=c.section,
                parent_id=c.parent_id,
                metadata=c.metadata,
                fused_score=c.fused_score,
                source_ranks=c.source_ranks,
                source_scores=c.source_scores,
            )
            for rank, c in enumerate(candidates[:top_k])
        ]


@pytest.fixture
def client(tmp_path: Path, ingestion_env: Path) -> TestClient:
    app = create_app()

    conn = get_connection(get_settings().sqlite_path)
    DocumentRepository(conn).upsert(
        DocumentUpsert(
            id="doc-1",
            filename="photosynthesis.pdf",
            file_type="pdf",
            file_hash="fake-hash",
            status="ready",
        )
    )
    conn.close()

    bm25 = BM25Retriever.from_chunks(CORPUS)
    provider = FakeEmbeddingProvider()
    store = FaissIndexStore.build(
        CORPUS, provider, tmp_path / "indexes", chunk_target_tokens=512, chunk_overlap_tokens=50
    )
    dense = DenseRetriever(store, provider, {c.id: c for c in CORPUS})

    app.dependency_overrides[retrieval_api.get_bm25_retriever] = lambda: bm25
    app.dependency_overrides[retrieval_api.get_dense_retriever] = lambda: dense
    app.dependency_overrides[retrieval_api.get_hyde_expander] = lambda: None
    app.dependency_overrides[retrieval_api.get_reranker] = lambda: _FakeReranker()
    app.dependency_overrides[chat_api.get_generator] = lambda: FakeGenerator(
        text="Photosynthesis converts light energy into chemical energy. [chunk:c1]",
        raw_chunk_ids=["c1"],
    )
    return TestClient(app)


def test_grounded_query_returns_structured_response(client: TestClient) -> None:
    response = client.post(
        "/chat/query",
        json={"query": "What is photosynthesis?", "retrieval_mode": "hybrid_rrf", "top_k": 2},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["answerable"] is True
    assert body["evidence"]
    assert body["timing"]["total_ms"] >= 0
    assert body["sufficiency"]["sufficient"] is True


def test_grounded_query_resolves_filename_from_document(client: TestClient) -> None:
    response = client.post(
        "/chat/query",
        json={"query": "What is photosynthesis?", "retrieval_mode": "hybrid_rrf", "top_k": 2},
    )
    body = response.json()
    # `c1`/`c2` chunk fixtures use document_id="doc-1" by default (see make_chunk).
    assert any(e["document_id"] == "doc-1" for e in body["evidence"])
    doc1_evidence = [e for e in body["evidence"] if e["document_id"] == "doc-1"]
    assert all(e["filename"] == "photosynthesis.pdf" for e in doc1_evidence)


def test_abstention_when_evidence_insufficient(client: TestClient) -> None:
    response = client.post(
        "/chat/query",
        json={
            "query": "zzz completely unrelated gibberish query xyzzy",
            "retrieval_mode": "bm25",
            "top_k": 2,
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["answerable"] is False
    assert body["citations"] == []


def test_provider_unavailable_returns_503(client: TestClient) -> None:
    client.app.dependency_overrides[chat_api.get_generator] = lambda: FakeGenerator(
        unavailable=True
    )
    response = client.post(
        "/chat/query",
        json={"query": "What is photosynthesis?", "retrieval_mode": "hybrid_rrf", "top_k": 2},
    )
    assert response.status_code == 503


def test_malformed_request_missing_query_returns_422(client: TestClient) -> None:
    response = client.post("/chat/query", json={"retrieval_mode": "bm25"})
    assert response.status_code == 422


def test_invalid_retrieval_mode_returns_400(client: TestClient) -> None:
    response = client.post(
        "/chat/query", json={"query": "What is photosynthesis?", "retrieval_mode": "not_a_mode"}
    )
    assert response.status_code == 400
