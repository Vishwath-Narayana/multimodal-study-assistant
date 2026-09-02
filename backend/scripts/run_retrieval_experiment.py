"""Runs the Phase 2 dev-benchmark retrieval experiment end to end and saves
a report under `backend/experiment-results/` (gitignored).

Uses REAL BM25 (rank-bm25), REAL BGE embeddings + FAISS
(`BAAI/bge-small-en-v1.5`, downloaded on first run), and a REAL
cross-encoder reranker (`cross-encoder/ms-marco-MiniLM-L-6-v2`). HyDE uses
a mocked `QueryExpander` (`tests.retrieval.fakes.FakeQueryExpander`)
instead of a real Ollama call, because Ollama is not available in this
environment — this is recorded explicitly in the report's `config` block
(`hyde_mocked: true`) rather than silently presented as a real HyDE run.

Run from `backend/`: `uv run python scripts/run_retrieval_experiment.py`
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tests"))

from retrieval.fakes import FakeQueryExpander  # tests/retrieval/fakes.py

from app.ingestion.chunking import ChunkingConfig
from app.ingestion.parsers.docling_parser import DoclingParser
from app.ingestion.repository import ChunkRepository, DocumentRepository, get_connection, init_db
from app.ingestion.service import IngestionService
from app.ingestion.storage import DataPaths, FileImageStorage
from app.retrieval.bm25_retriever import BM25Retriever
from app.retrieval.dense_retriever import DenseRetriever
from app.retrieval.embeddings import BGEEmbeddingProvider
from app.retrieval.evaluation.dataset import load_eval_dataset
from app.retrieval.evaluation.runner import ExperimentRunner
from app.retrieval.faiss_index import FaissIndexStore
from app.retrieval.models import RetrievalMode
from app.retrieval.reranker import CrossEncoderReranker
from app.retrieval.rrf import RRFFusion
from app.retrieval.service import RetrievalService, RetrievalServiceConfig

FIXTURES_DIR = Path(__file__).resolve().parents[1] / "tests" / "fixtures"
SCRATCH_DIR = Path("/tmp/retrieval_experiment_scratch")
RESULTS_DIR = Path(__file__).resolve().parents[1] / "experiment-results"


def main() -> None:
    SCRATCH_DIR.mkdir(exist_ok=True)
    data_paths = DataPaths(str(SCRATCH_DIR / "data"))
    image_storage = FileImageStorage(data_paths)
    parser = DoclingParser(image_storage=image_storage)

    conn = get_connection(str(SCRATCH_DIR / "app.db"))
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
        print(f"ingested {fixture_name}: status={result.status} chunks={result.chunk_count}")

    chunks = ChunkRepository(conn).list_all()
    print(f"total chunks: {len(chunks)}")

    bm25 = BM25Retriever.from_chunks(chunks)

    embedding_provider = BGEEmbeddingProvider("BAAI/bge-small-en-v1.5", batch_size=32)
    store = FaissIndexStore.build(
        chunks,
        embedding_provider,
        SCRATCH_DIR / "indexes",
        chunk_target_tokens=512,
        chunk_overlap_tokens=50,
    )
    dense = DenseRetriever(store, embedding_provider, {c.id: c for c in chunks})

    hyde = FakeQueryExpander(
        hypothetical_text=(
            "This is a mocked HyDE passage used because no local Ollama server "
            "was available in this environment."
        )
    )
    reranker = CrossEncoderReranker("cross-encoder/ms-marco-MiniLM-L-6-v2")

    config = RetrievalServiceConfig(
        bm25_top_k=20,
        dense_top_k=20,
        rrf_k=60,
        rrf_candidate_k=20,
        rerank_candidate_k=20,
        final_top_k=5,
    )
    service = RetrievalService(bm25, dense, hyde, RRFFusion(k=60), reranker, config)

    dataset = load_eval_dataset()
    runner = ExperimentRunner(service, dataset, top_k=5)
    modes = [
        RetrievalMode.BM25,
        RetrievalMode.DENSE,
        RetrievalMode.DENSE_HYDE,
        RetrievalMode.HYBRID_RRF,
        RetrievalMode.HYBRID_RRF_HYDE,
        RetrievalMode.FULL_BASELINE,
    ]
    report = runner.run(
        modes,
        config={
            "embedding_model": embedding_provider.model_id,
            "embedding_dimension": embedding_provider.dimension,
            "reranker_model": reranker.model_id,
            "hyde_model": "MOCKED (no Ollama available in this environment)",
            "hyde_mocked": True,
            "rrf_k": 60,
            "bm25_top_k": config.bm25_top_k,
            "dense_top_k": config.dense_top_k,
            "rrf_candidate_k": config.rrf_candidate_k,
            "rerank_candidate_k": config.rerank_candidate_k,
            "final_top_k": config.final_top_k,
            "chunk_count": len(chunks),
        },
    )

    for mode_result in report.modes:
        print(f"\n=== {mode_result.mode} ===")
        for key, value in mode_result.aggregate_metrics.items():
            print(f"  {key}: {value:.3f}")

    out_path = report.save(RESULTS_DIR)
    print(f"\nSaved report to {out_path}")


if __name__ == "__main__":
    main()
