"""End-to-end retrieval test: real Phase 1 ingestion -> real BM25 index ->
real FAISS index (deterministic fake embeddings, not a real model download,
per the Phase 2 spec's testing requirements) -> RetrievalService -> query.

bm25 / dense / hybrid_rrf are exercised for real, end to end. dense_hyde /
hybrid_rrf_hyde / full_baseline are exercised with a mocked HyDE provider
and a mocked reranker (real cross-encoder/Ollama inference is not run in
the default test suite — see test_hyde_integration.py for the marked,
opt-in real-Ollama test).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.ingestion.chunking import ChunkingConfig
from app.ingestion.parsers.docling_parser import DoclingParser
from app.ingestion.repository import ChunkRepository, DocumentRepository, get_connection, init_db
from app.ingestion.service import IngestionService
from app.ingestion.storage import DataPaths, FileImageStorage
from app.retrieval.bm25_retriever import BM25Retriever
from app.retrieval.dense_retriever import DenseRetriever
from app.retrieval.faiss_index import FaissIndexStore
from app.retrieval.models import RetrievalMode, RetrievalSource
from app.retrieval.rrf import RRFFusion
from app.retrieval.service import RetrievalService, RetrievalServiceConfig
from tests.retrieval.fakes import FakeEmbeddingProvider, FakeQueryExpander

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures"


class _FakeCrossEncoder:
    def predict(self, pairs: list[tuple[str, str]]) -> list[float]:
        # Deterministic score based on lexical overlap, no model download.
        scores = []
        for query, content in pairs:
            q_words = set(query.lower().split())
            c_words = set(content.lower().split())
            scores.append(float(len(q_words & c_words)))
        return scores


@pytest.fixture
def retrieval_service(tmp_path: Path) -> RetrievalService:
    data_paths = DataPaths(str(tmp_path / "data"))
    image_storage = FileImageStorage(data_paths)
    parser = DoclingParser(image_storage=image_storage)

    db_path = tmp_path / "app.db"
    conn = get_connection(str(db_path))
    init_db(conn)

    ingestion = IngestionService(
        parser=parser,
        document_repo=DocumentRepository(conn),
        chunk_repo=ChunkRepository(conn),
        data_paths=data_paths,
        supported_extensions=("html", "htm", "docx", "pptx", "pdf"),
        max_upload_size_bytes=50 * 1024 * 1024,
        chunking_config=ChunkingConfig(target_tokens=512, overlap_tokens=50),
    )

    for fixture_name in ["study_notes.html", "study_notes.docx", "study_notes.pptx"]:
        data = (FIXTURES_DIR / fixture_name).read_bytes()
        result = ingestion.ingest(fixture_name, data)
        assert result.status == "completed"

    chunks = ChunkRepository(conn).list_all()
    assert chunks  # real ingestion produced real chunks

    bm25 = BM25Retriever.from_chunks(chunks)

    provider = FakeEmbeddingProvider()
    store = FaissIndexStore.build(
        chunks, provider, tmp_path / "indexes", chunk_target_tokens=512, chunk_overlap_tokens=50
    )
    dense = DenseRetriever(store, provider, {c.id: c for c in chunks})

    hyde = FakeQueryExpander(
        hypothetical_text="Photosynthesis converts light energy into chemical energy."
    )
    reranker_model = _FakeCrossEncoder()
    from app.retrieval.reranker import CrossEncoderReranker

    reranker = CrossEncoderReranker("fake-reranker")
    reranker._model = reranker_model

    config = RetrievalServiceConfig(
        bm25_top_k=10,
        dense_top_k=10,
        rrf_k=60,
        rrf_candidate_k=20,
        rerank_candidate_k=20,
        final_top_k=5,
    )
    return RetrievalService(bm25, dense, hyde, RRFFusion(k=60), reranker, config)


def test_bm25_mode_end_to_end(retrieval_service: RetrievalService) -> None:
    results, trace = retrieval_service.retrieve(
        "photosynthesis chemical energy", RetrievalMode.BM25, top_k=3
    )
    assert results
    assert all(r.retrieval_source == RetrievalSource.BM25 for r in results)
    assert trace.timings.bm25_ms is not None


def test_dense_mode_end_to_end(retrieval_service: RetrievalService) -> None:
    results, _ = retrieval_service.retrieve(
        "cellular respiration glucose", RetrievalMode.DENSE, top_k=3
    )
    assert results
    assert all(r.retrieval_source == RetrievalSource.DENSE for r in results)


def test_hybrid_rrf_mode_end_to_end(retrieval_service: RetrievalService) -> None:
    results, trace = retrieval_service.retrieve(
        "mitochondria ATP production", RetrievalMode.HYBRID_RRF, top_k=3
    )
    assert results
    assert all(r.retrieval_source == RetrievalSource.RRF for r in results)
    assert trace.bm25_candidates and trace.dense_candidates


def test_dense_hyde_mode_end_to_end_with_mocked_hyde(retrieval_service: RetrievalService) -> None:
    results, trace = retrieval_service.retrieve("energy", RetrievalMode.DENSE_HYDE, top_k=3)
    assert results
    assert trace.hyde_query


def test_full_baseline_mode_end_to_end_with_mocks(retrieval_service: RetrievalService) -> None:
    results, trace = retrieval_service.retrieve(
        "photosynthesis", RetrievalMode.FULL_BASELINE, top_k=3
    )
    assert results
    assert all(r.retrieval_source == RetrievalSource.RERANKER for r in results)
    assert trace.rerank_candidates
