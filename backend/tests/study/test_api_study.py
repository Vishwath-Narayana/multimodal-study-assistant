from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.api import retrieval as retrieval_api
from app.api import study as study_api
from app.core.config import get_settings
from app.ingestion.repository import DocumentRepository, DocumentUpsert, get_connection
from app.main import create_app
from app.retrieval.bm25_retriever import BM25Retriever
from app.retrieval.dense_retriever import DenseRetriever
from app.retrieval.faiss_index import FaissIndexStore
from tests.retrieval.conftest import make_chunk
from tests.retrieval.fakes import FakeEmbeddingProvider
from tests.study.fakes import FakeStudyGenerator

CORPUS = [
    make_chunk("c1", "BM25 is a bag-of-words lexical ranking function used for retrieval.", page=1),
    make_chunk("c2", "Dense retrieval uses embeddings to find semantically similar text.", page=2),
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
            filename="retrieval-notes.pdf",
            file_type="pdf",
            file_hash="hash",
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
    app.dependency_overrides[study_api.get_study_generator] = lambda: FakeStudyGenerator()
    return TestClient(app)


def test_summary_endpoint_returns_grounded_item(client: TestClient) -> None:
    response = client.post(
        "/study/summary",
        json={"query": "What is BM25?", "retrieval_mode": "hybrid_rrf", "top_k": 2},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["answerable"] is True
    assert body["item"]["content"]
    assert body["evidence"]


def test_explain_endpoint(client: TestClient) -> None:
    response = client.post(
        "/study/explain",
        json={
            "query": "What is BM25?",
            "retrieval_mode": "hybrid_rrf",
            "top_k": 2,
            "style": "simple",
        },
    )
    assert response.status_code == 200
    assert response.json()["answerable"] is True


def test_compare_endpoint(client: TestClient) -> None:
    response = client.post(
        "/study/compare",
        json={
            "topic_a": "BM25",
            "topic_b": "dense retrieval",
            "retrieval_mode": "hybrid_rrf",
            "top_k": 2,
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["item"]["aspects"]


def test_quiz_endpoint_returns_items(client: TestClient) -> None:
    response = client.post(
        "/study/quiz",
        json={"query": "BM25", "retrieval_mode": "hybrid_rrf", "top_k": 2, "count": 1},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["answerable"] is True
    assert len(body["items"]) == 1
    assert body["items"][0]["source_chunk_ids"]


def test_mcq_endpoint_returns_four_options(client: TestClient) -> None:
    response = client.post(
        "/study/mcq",
        json={"query": "BM25", "retrieval_mode": "hybrid_rrf", "top_k": 2, "count": 1},
    )
    assert response.status_code == 200
    body = response.json()
    assert len(body["items"][0]["options"]) == 4
    assert body["items"][0]["correct_option"] == "A"


def test_flashcards_endpoint_returns_items(client: TestClient) -> None:
    response = client.post(
        "/study/flashcards",
        json={"query": "BM25", "retrieval_mode": "hybrid_rrf", "top_k": 2, "count": 1},
    )
    assert response.status_code == 200
    assert response.json()["items"][0]["front"]


def test_quiz_invalid_count_returns_400(client: TestClient) -> None:
    response = client.post(
        "/study/quiz",
        json={"query": "BM25", "retrieval_mode": "hybrid_rrf", "top_k": 2, "count": 999},
    )
    assert response.status_code == 400


def test_abstention_when_evidence_insufficient(client: TestClient) -> None:
    response = client.post(
        "/study/summary",
        json={
            "query": "zzz completely unrelated gibberish xyzzy",
            "retrieval_mode": "bm25",
            "top_k": 2,
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["answerable"] is False
    assert body["item"] is None


def test_provider_unavailable_returns_503(client: TestClient) -> None:
    client.app.dependency_overrides[study_api.get_study_generator] = lambda: FakeStudyGenerator(
        unavailable=True
    )
    response = client.post(
        "/study/summary",
        json={"query": "What is BM25?", "retrieval_mode": "hybrid_rrf", "top_k": 2},
    )
    assert response.status_code == 503


def test_malformed_llm_output_returns_502(client: TestClient) -> None:
    client.app.dependency_overrides[study_api.get_study_generator] = lambda: FakeStudyGenerator(
        quiz_text="not json at all"
    )
    response = client.post(
        "/study/quiz",
        json={"query": "BM25", "retrieval_mode": "hybrid_rrf", "top_k": 2, "count": 1},
    )
    assert response.status_code == 502


def test_malformed_request_missing_query_returns_422(client: TestClient) -> None:
    response = client.post("/study/summary", json={"retrieval_mode": "bm25"})
    assert response.status_code == 422


def test_invalid_retrieval_mode_returns_400(client: TestClient) -> None:
    response = client.post(
        "/study/summary", json={"query": "What is BM25?", "retrieval_mode": "not_a_mode"}
    )
    assert response.status_code == 400


def test_document_scope_filters_evidence(client: TestClient) -> None:
    response = client.post(
        "/study/summary",
        json={
            "query": "What is BM25?",
            "retrieval_mode": "hybrid_rrf",
            "top_k": 2,
            "document_id": "doc-1",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert all(e["document_id"] == "doc-1" for e in body["evidence"])


def test_document_scope_to_unknown_document_abstains(client: TestClient) -> None:
    response = client.post(
        "/study/summary",
        json={
            "query": "What is BM25?",
            "retrieval_mode": "hybrid_rrf",
            "top_k": 2,
            "document_id": "doc-does-not-exist",
        },
    )
    assert response.status_code == 200
    assert response.json()["answerable"] is False
