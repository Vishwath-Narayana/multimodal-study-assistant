"""Builds a real, fully-wired retrieval stack for Phase 7 evaluation runs.

Reuses the exact production components (`BM25Retriever`, `DenseRetriever`,
`RRFFusion`, `CrossEncoderReranker`) the same way `scripts/
run_retrieval_experiment.py` does for Phase 2 — no second retrieval
implementation. The only new thing here is that `ChunkingConfig` is a
parameter, so the same wiring can build a corpus under the baseline
chunking (whitespace token counter) or the Phase 7F.2 BGE-token-aware
variant (see `chunking_variants.py`).
"""

from __future__ import annotations

import shutil
import tempfile
import uuid
from dataclasses import dataclass
from pathlib import Path

from app.ingestion.chunking import ChunkingConfig
from app.ingestion.models import Chunk
from app.ingestion.parsers.docling_parser import DoclingParser
from app.ingestion.repository import ChunkRepository, DocumentRepository, get_connection, init_db
from app.ingestion.service import IngestionService
from app.ingestion.storage import DataPaths, FileImageStorage
from app.retrieval.bm25_retriever import BM25Retriever
from app.retrieval.dense_retriever import DenseRetriever
from app.retrieval.embeddings import BGEEmbeddingProvider
from app.retrieval.faiss_index import FaissIndexStore
from app.retrieval.reranker import CrossEncoderReranker
from app.retrieval.rrf import RRFFusion
from app.retrieval.service import RetrievalService, RetrievalServiceConfig

FIXTURES_DIR = Path(__file__).resolve().parents[2] / "tests" / "fixtures"
PILOT_FIXTURE_FILES = ["study_notes.html", "study_notes.docx", "study_notes.pptx"]

EMBEDDING_MODEL = "BAAI/bge-small-en-v1.5"
RERANKER_MODEL = "cross-encoder/ms-marco-MiniLM-L-6-v2"


@dataclass
class RealStack:
    """Everything a Phase 7 runner needs: the orchestrating service, the raw
    components (for eval-only compositions the service doesn't expose,
    e.g. hybrid+reranker without HyDE), and corpus stats for the manifest.
    """

    service: RetrievalService
    bm25: BM25Retriever
    dense: DenseRetriever
    fusion: RRFFusion
    reranker: CrossEncoderReranker
    chunks: list[Chunk]
    embedding_model: str
    reranker_model: str
    scratch_dir: Path

    def cleanup(self) -> None:
        shutil.rmtree(self.scratch_dir, ignore_errors=True)


def build_real_stack(
    chunking_config: ChunkingConfig | None = None,
    top_k: int = 10,
    rrf_k: int = 60,
) -> RealStack:
    """Ingests the real pilot fixtures and wires up real BM25/dense/RRF/
    reranker components. No HyDE (no `QueryExpander` is passed in) — Ollama
    is not available in this environment, so HyDE-dependent modes are
    handled separately and explicitly labeled (see `hyde_ablation.py`).
    """
    chunking_config = chunking_config or ChunkingConfig(target_tokens=512, overlap_tokens=50)
    scratch_dir = Path(tempfile.mkdtemp(prefix="phase7_eval_"))
    data_paths = DataPaths(str(scratch_dir / "data"))
    image_storage = FileImageStorage(data_paths)
    parser = DoclingParser(image_storage=image_storage)

    conn = get_connection(str(scratch_dir / "app.db"))
    init_db(conn)

    ingestion = IngestionService(
        parser=parser,
        document_repo=DocumentRepository(conn),
        chunk_repo=ChunkRepository(conn),
        data_paths=data_paths,
        supported_extensions=("html", "htm", "docx", "pptx", "pdf"),
        max_upload_size_bytes=50 * 1024 * 1024,
        chunking_config=chunking_config,
    )
    for fixture_name in PILOT_FIXTURE_FILES:
        data = (FIXTURES_DIR / fixture_name).read_bytes()
        ingestion.ingest(fixture_name, data)

    chunks = ChunkRepository(conn).list_all()

    bm25 = BM25Retriever.from_chunks(chunks)

    embedding_provider = BGEEmbeddingProvider(EMBEDDING_MODEL, batch_size=32)
    store = FaissIndexStore.build(
        chunks,
        embedding_provider,
        scratch_dir / "indexes" / uuid.uuid4().hex,
        chunk_target_tokens=chunking_config.target_tokens,
        chunk_overlap_tokens=chunking_config.overlap_tokens,
    )
    dense = DenseRetriever(store, embedding_provider, {c.id: c for c in chunks})

    fusion = RRFFusion(k=rrf_k)
    reranker = CrossEncoderReranker(RERANKER_MODEL)

    config = RetrievalServiceConfig(
        bm25_top_k=20,
        dense_top_k=20,
        rrf_k=rrf_k,
        rrf_candidate_k=20,
        rerank_candidate_k=20,
        final_top_k=top_k,
    )
    # hyde_expander=None: any HyDE-dependent mode raises HyDEUnavailableError
    # if invoked through `service`, by design — see hyde_ablation.py for the
    # explicitly-labeled mocked-HyDE path used only for pipeline validation.
    service = RetrievalService(bm25, dense, None, fusion, reranker, config)

    return RealStack(
        service=service,
        bm25=bm25,
        dense=dense,
        fusion=fusion,
        reranker=reranker,
        chunks=chunks,
        embedding_model=embedding_provider.model_id,
        reranker_model=reranker.model_id,
        scratch_dir=scratch_dir,
    )
