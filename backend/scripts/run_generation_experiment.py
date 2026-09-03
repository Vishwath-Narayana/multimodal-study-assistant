"""Runs the Phase 3 ablation comparison (spec section 21 / docs/research/
ablation-plan.md rows A-G) and saves a report under
`backend/experiment-results/` (gitignored).

Uses the same REAL retrieval stack as `run_retrieval_experiment.py`
(BM25, BGE + FAISS, cross-encoder reranker) over the Phase 1 fixture
corpus, running `full_baseline` retrieval for every dev-dataset query.
Generation uses a deterministic MOCK generator by default (no Ollama
required) — pass `--ollama` to use a real local Ollama server instead, if
one is reachable and the configured model is pulled. Either way, which one
ran is recorded explicitly in the report (`generation_mocked: true/false`),
never silently presented as the other (spec: "never fabricate real model
benchmark results").

The current Phase 2 dev dataset (`app.retrieval.evaluation.dataset`) has no
reference answer text, so generation-quality metrics that need one
(Token F1, ROUGE-L, BERTScore — see `app.generation.evaluation.metrics`)
cannot be computed here. This script reports what *is* computable without a
reference answer for each ablation stage: citation validity rate,
mean token grounding ratio, and contradiction rate.

Run from `backend/`: `uv run python scripts/run_generation_experiment.py`
"""

from __future__ import annotations

import json
import sys
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tests"))

from generation.fakes import FakeGenerator  # tests/generation/fakes.py
from retrieval.fakes import FakeQueryExpander  # tests/retrieval/fakes.py

from app.generation.attribution import DeterministicChunkAttributor
from app.generation.citations import DeterministicCitationValidator
from app.generation.claims import DeterministicClaimSplitter
from app.generation.contradiction import LexicalContradictionChecker
from app.generation.errors import GenerationError
from app.generation.generator import OllamaGenerator
from app.generation.interfaces import Generator
from app.generation.service import GenerationService, GenerationServiceConfig
from app.generation.sufficiency import HeuristicSufficiencyChecker, SufficiencyConfig
from app.generation.token_grounding import DeterministicTokenGrounder
from app.ingestion.chunking import ChunkingConfig
from app.ingestion.parsers.docling_parser import DoclingParser
from app.ingestion.repository import ChunkRepository, DocumentRepository, get_connection, init_db
from app.ingestion.service import IngestionService
from app.ingestion.storage import DataPaths, FileImageStorage
from app.retrieval.bm25_retriever import BM25Retriever
from app.retrieval.dense_retriever import DenseRetriever
from app.retrieval.embeddings import BGEEmbeddingProvider
from app.retrieval.evaluation.dataset import load_eval_dataset
from app.retrieval.faiss_index import FaissIndexStore
from app.retrieval.llm_client import OllamaClient
from app.retrieval.models import RetrievalMode
from app.retrieval.reranker import CrossEncoderReranker
from app.retrieval.rrf import RRFFusion
from app.retrieval.service import RetrievalService, RetrievalServiceConfig

FIXTURES_DIR = Path(__file__).resolve().parents[1] / "tests" / "fixtures"
SCRATCH_DIR = Path("/tmp/generation_experiment_scratch")
RESULTS_DIR = Path(__file__).resolve().parents[1] / "experiment-results"
OLLAMA_MODEL = "deepseek-r1:8b"
OLLAMA_BASE_URL = "http://localhost:11434"

# Ablation stages (docs/research/ablation-plan.md rows A-G), expressed as
# GenerationServiceConfig toggles plus whether stage A's plain (ungrounded)
# prompt is used instead of the grounded one.
STAGES: dict[str, dict[str, bool]] = {
    "A_plain_generation": {
        "use_grounded_prompt": False,
        "enable_sufficiency_check": False,
        "enable_citation_validation": False,
        "enable_attribution": False,
        "enable_token_grounding": False,
        "enable_claim_grounding": False,
        "enable_contradiction_check": False,
    },
    "B_grounded_prompt": {
        "use_grounded_prompt": True,
        "enable_sufficiency_check": False,
        "enable_citation_validation": False,
        "enable_attribution": False,
        "enable_token_grounding": False,
        "enable_claim_grounding": False,
        "enable_contradiction_check": False,
    },
    "C_plus_sufficiency": {
        "use_grounded_prompt": True,
        "enable_sufficiency_check": True,
        "enable_citation_validation": False,
        "enable_attribution": False,
        "enable_token_grounding": False,
        "enable_claim_grounding": False,
        "enable_contradiction_check": False,
    },
    "D_plus_citation_validation": {
        "use_grounded_prompt": True,
        "enable_sufficiency_check": True,
        "enable_citation_validation": True,
        "enable_attribution": False,
        "enable_token_grounding": False,
        "enable_claim_grounding": False,
        "enable_contradiction_check": False,
    },
    "E_plus_attribution": {
        "use_grounded_prompt": True,
        "enable_sufficiency_check": True,
        "enable_citation_validation": True,
        "enable_attribution": True,
        "enable_token_grounding": False,
        "enable_claim_grounding": False,
        "enable_contradiction_check": False,
    },
    "F_plus_token_grounding": {
        "use_grounded_prompt": True,
        "enable_sufficiency_check": True,
        "enable_citation_validation": True,
        "enable_attribution": True,
        "enable_token_grounding": True,
        "enable_claim_grounding": True,
        "enable_contradiction_check": False,
    },
    "G_full_pipeline": {
        "use_grounded_prompt": True,
        "enable_sufficiency_check": True,
        "enable_citation_validation": True,
        "enable_attribution": True,
        "enable_token_grounding": True,
        "enable_claim_grounding": True,
        "enable_contradiction_check": True,
    },
}


@dataclass
class StagePerQuery:
    query_id: str
    query: str
    answerable: bool
    citation_valid_count: int
    citation_total_count: int
    grounding_ratio: float | None
    has_conflict: bool
    error: str | None = None


@dataclass
class StageResult:
    stage: str
    config: dict[str, bool]
    answerable_rate: float
    citation_validity_rate: float | None
    mean_grounding_ratio: float | None
    conflict_rate: float
    per_query: list[StagePerQuery] = field(default_factory=list)


@dataclass
class GenerationExperimentReport:
    timestamp: str
    generation_mocked: bool
    generation_provider: str
    generation_model: str
    query_count: int
    stages: list[StageResult] = field(default_factory=list)

    def save(self, output_dir: str | Path) -> Path:
        path = Path(output_dir)
        path.mkdir(parents=True, exist_ok=True)
        filename = f"generation-experiment-{self.timestamp.replace(':', '').replace('.', '')}.json"
        out_path = path / filename
        out_path.write_text(json.dumps(asdict(self), indent=2))
        return out_path


def _build_retrieval_service() -> tuple[RetrievalService, int]:
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
        ingestion.ingest(fixture_name, data)

    chunks = ChunkRepository(conn).list_all()
    bm25 = BM25Retriever.from_chunks(chunks)
    embedding_provider = BGEEmbeddingProvider("BAAI/bge-small-en-v1.5", batch_size=32)
    store = FaissIndexStore.build(
        chunks, embedding_provider, SCRATCH_DIR / "indexes", chunk_target_tokens=512,
        chunk_overlap_tokens=50,
    )
    dense = DenseRetriever(store, embedding_provider, {c.id: c for c in chunks})
    hyde = FakeQueryExpander(hypothetical_text="Mocked HyDE passage (no Ollama in this run).")
    reranker = CrossEncoderReranker("cross-encoder/ms-marco-MiniLM-L-6-v2")
    config = RetrievalServiceConfig(
        bm25_top_k=20, dense_top_k=20, rrf_k=60, rrf_candidate_k=20, rerank_candidate_k=20,
        final_top_k=5,
    )
    return RetrievalService(bm25, dense, hyde, RRFFusion(k=60), reranker, config), len(chunks)


def _build_generator(use_grounded_prompt: bool, use_ollama: bool) -> tuple[Generator, bool]:
    if use_ollama:
        client = OllamaClient(OLLAMA_BASE_URL, OLLAMA_MODEL)
        if client.is_reachable():
            return OllamaGenerator(client, use_grounded_prompt=use_grounded_prompt), False
        print(f"Ollama not reachable/model '{OLLAMA_MODEL}' unavailable — falling back to mock.")
    return FakeGenerator(text="This is a mocked answer for the ablation experiment."), True


def _build_service(stage_config: dict[str, bool], generator: Generator) -> GenerationService:
    sufficiency = HeuristicSufficiencyChecker(SufficiencyConfig(1, 0.08, 0.0))
    token_grounder = DeterministicTokenGrounder()
    service_config = GenerationServiceConfig(
        max_tokens=256,
        temperature=0.2,
        enable_sufficiency_check=stage_config["enable_sufficiency_check"],
        enable_citation_validation=stage_config["enable_citation_validation"],
        enable_attribution=stage_config["enable_attribution"],
        enable_token_grounding=stage_config["enable_token_grounding"],
        enable_claim_grounding=stage_config["enable_claim_grounding"],
        enable_contradiction_check=stage_config["enable_contradiction_check"],
    )
    return GenerationService(
        generator=generator,
        sufficiency_checker=sufficiency,
        citation_validator=DeterministicCitationValidator(),
        attributor=DeterministicChunkAttributor(),
        token_grounder=token_grounder,
        claim_splitter=DeterministicClaimSplitter(token_grounder),
        contradiction_checker=LexicalContradictionChecker(),
        config=service_config,
    )


def main() -> None:
    use_ollama = "--ollama" in sys.argv
    retrieval_service, chunk_count = _build_retrieval_service()
    dataset = load_eval_dataset()

    report = GenerationExperimentReport(
        timestamp=datetime.now(UTC).isoformat(),
        generation_mocked=True,
        generation_provider="",
        generation_model="",
        query_count=len(dataset.queries),
    )

    for stage_name, stage_config in STAGES.items():
        generator, mocked = _build_generator(stage_config["use_grounded_prompt"], use_ollama)
        if stage_name == "A_plain_generation":
            report.generation_mocked = mocked
            report.generation_provider = generator.provider_id
            report.generation_model = generator.model_id

        service = _build_service(stage_config, generator)
        per_query: list[StagePerQuery] = []
        for query in dataset.queries:
            try:
                evidence, _trace = retrieval_service.retrieve(
                    query.query, RetrievalMode.FULL_BASELINE, top_k=5
                )
                response = service.answer(query.query, evidence)
                valid = sum(1 for c in response.citations if c.valid)
                per_query.append(
                    StagePerQuery(
                        query_id=query.query_id,
                        query=query.query,
                        answerable=response.answerable,
                        citation_valid_count=valid,
                        citation_total_count=len(response.citations),
                        grounding_ratio=(
                            response.grounding.grounding_ratio if response.grounding else None
                        ),
                        has_conflict=response.contradictions.has_conflict,
                    )
                )
            except GenerationError as exc:
                per_query.append(
                    StagePerQuery(
                        query_id=query.query_id,
                        query=query.query,
                        answerable=False,
                        citation_valid_count=0,
                        citation_total_count=0,
                        grounding_ratio=None,
                        has_conflict=False,
                        error=f"{type(exc).__name__}: {exc.message}",
                    )
                )

        n = len(per_query) or 1
        total_citations = sum(p.citation_total_count for p in per_query)
        valid_citations = sum(p.citation_valid_count for p in per_query)
        grounding_ratios = [p.grounding_ratio for p in per_query if p.grounding_ratio is not None]

        report.stages.append(
            StageResult(
                stage=stage_name,
                config=stage_config,
                answerable_rate=sum(1 for p in per_query if p.answerable) / n,
                citation_validity_rate=(
                    valid_citations / total_citations if total_citations else None
                ),
                mean_grounding_ratio=(
                    sum(grounding_ratios) / len(grounding_ratios) if grounding_ratios else None
                ),
                conflict_rate=sum(1 for p in per_query if p.has_conflict) / n,
                per_query=per_query,
            )
        )
        print(f"stage {stage_name}: answerable_rate={report.stages[-1].answerable_rate:.2f}")

    print(f"\nchunks indexed: {chunk_count}")
    print(
        f"generation_mocked: {report.generation_mocked} "
        f"({report.generation_provider}/{report.generation_model})"
    )
    out_path = report.save(RESULTS_DIR)
    print(f"Saved report to {out_path}")


if __name__ == "__main__":
    main()
