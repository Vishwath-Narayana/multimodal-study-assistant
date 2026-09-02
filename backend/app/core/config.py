from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# The repository root's data/ directory (see docs/architecture/system-architecture.md
# repo layout) — computed from this file's location rather than the process's
# current working directory, so `data_dir`/`database_url` resolve correctly
# whether the app is launched from the repo root or from backend/ (as
# documented in backend/README.md).
_REPO_ROOT = Path(__file__).resolve().parents[3]
_DEFAULT_DATA_DIR = _REPO_ROOT / "data"


class Settings(BaseSettings):
    """Application configuration, loaded from environment variables / .env."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "development"
    log_level: str = "INFO"

    database_url: str = f"sqlite:///{_DEFAULT_DATA_DIR / 'app.db'}"

    embedding_model: str = "BAAI/bge-small-en-v1.5"
    reranker_model: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"

    # Implementation choice: the frontend and backend run as separate dev
    # servers (Vite on 5173, FastAPI on 8000), so CORS must be configured
    # even for purely local development.
    cors_allowed_origins: str = "http://localhost:5173"

    # --- Generation (Phase 3) ---
    # Research baseline: DeepSeek-R1 8B served locally through Ollama (see
    # docs/architecture/generation.md). Distinct from `hyde_model` below,
    # which is a smaller model used only for HyDE query expansion.
    llm_provider: str = "ollama"
    llm_model: str = "deepseek-r1:8b"

    # Implementation choice: deterministic/low-temperature by default, to
    # favour reproducibility for a study assistant over creative variation.
    # Not mandated by EduRAG.
    generation_max_tokens: int = 512
    generation_temperature: float = 0.2
    generation_timeout_seconds: float = 120.0

    # Evidence sufficiency / abstention (spec section 8). Thresholds are
    # implementation choices, not EduRAG-specified or scientifically
    # validated values — see app.generation.sufficiency for exactly how
    # they are used and docs/architecture/generation.md "Limitations".
    sufficiency_min_chunks: int = 1
    sufficiency_min_lexical_overlap: float = 0.08
    sufficiency_min_reranker_score: float = 0.0

    # EduRAG baseline: deterministic chunk attribution weighting
    # (0.7 x cross-encoder relevance + 0.3 x lexical overlap). See
    # app.generation.attribution.
    attribution_relevance_weight: float = 0.7
    attribution_lexical_weight: float = 0.3

    # Token grounding "grounded" cutoff (score >= this counts as grounded
    # for the grounded/total token counts). The EduRAG matching-hierarchy
    # scores themselves (1.0/0.9/0.8/0.2) are fixed baseline values, not
    # configurable — see app.generation.token_grounding.
    grounding_threshold: float = 0.8

    # Contradiction checking: minimum lexical (Jaccard) overlap between two
    # evidence chunks before they are even considered as a candidate
    # conflicting pair. See app.generation.contradiction.
    contradiction_topic_overlap_threshold: float = 0.2

    vlm_provider: str = ""
    vlm_model: str = ""

    # --- Ingestion (Phase 1) ---
    # Data directory root. raw/ holds uploaded source files, processed/ holds
    # per-document derived artifacts (currently: extracted images).
    data_dir: str = str(_DEFAULT_DATA_DIR)

    # Supported upload extensions (without the leading dot), lowercase,
    # comma-separated. Implementation choice: EduRAG's baseline does not
    # enumerate a fixed format list, so this is our own scope decision for
    # Phase 1. Use `supported_extensions` for the parsed tuple.
    supported_extensions_raw: str = "pdf,docx,pptx,html,htm"

    # Implementation choice: 50MB is a local-first sanity limit, not a value
    # specified by the baseline paper.
    max_upload_size_mb: int = 50

    # EduRAG baseline: approximately 512 tokens per chunk.
    chunk_target_tokens: int = 512

    # Implementation choice: the baseline paper does not specify a chunk
    # overlap value, so this is our own engineering choice, kept small
    # relative to chunk_target_tokens.
    chunk_overlap_tokens: int = 50

    # --- Retrieval (Phase 2) ---
    # Where generated (not source-controlled) retrieval artifacts live:
    # FAISS index files + manifest, and BM25... (BM25 is rebuilt in-memory,
    # nothing persisted for it yet). Sibling of data_dir/raw and
    # data_dir/processed, same "generated, gitignored" convention.
    index_dir: str = str(_DEFAULT_DATA_DIR / "indexes")

    # EduRAG baseline: BM25 top-K candidates before fusion.
    bm25_top_k: int = 20

    # EduRAG baseline: dense (FAISS) top-K candidates before fusion.
    dense_top_k: int = 20

    # Implementation choice: batch size for embedding chunks/queries with
    # BGEEmbeddingProvider. Not specified by the baseline; chosen for
    # reasonable CPU throughput without large memory spikes.
    embedding_batch_size: int = 32

    # EduRAG baseline: Reciprocal Rank Fusion constant k=60 (the standard
    # RRF default from Cormack et al., which EduRAG adopts unchanged).
    rrf_k: int = 60

    # Implementation choice: how many fused RRF candidates are kept before
    # being handed to the reranker. EduRAG's baseline figure (RRF pool top
    # 20 -> reranker) — see docs/architecture/retrieval.md for the citation
    # caveat. Kept as its own setting (rather than reusing bm25/dense top_k)
    # because fused-list truncation is a distinct decision point.
    rrf_candidate_k: int = 20

    # EduRAG baseline: reranker candidate pool size (top 20 RRF results are
    # rescored by the cross-encoder).
    rerank_candidate_k: int = 20

    # EduRAG baseline: final evidence set size after reranking.
    final_top_k: int = 5

    # Implementation choice: HyDE is off by default so `bm25`/`dense`/
    # `hybrid_rrf` modes never depend on an LLM being reachable; callers opt
    # in per-request (mode=dense_hyde/hybrid_rrf_hyde/full_baseline) or via
    # this default.
    hyde_enabled: bool = False

    # Preferred baseline model per the project brief: DeepSeek-R1 1.5B via
    # Ollama. Implementation choice: served locally, not fetched by CI.
    hyde_model: str = "deepseek-r1:1.5b"

    # Implementation choice: local Ollama HTTP API base URL.
    ollama_base_url: str = "http://localhost:11434"

    # Implementation choice: HyDE generation is deliberately short (a
    # "concise hypothetical passage", not a full answer) and deterministic
    # temperature is not mandated by EduRAG — low temperature here favours
    # reproducibility over diversity.
    hyde_max_tokens: int = 256
    hyde_temperature: float = 0.2

    # Implementation choice: HTTP timeout for the local Ollama call.
    hyde_timeout_seconds: float = 30.0

    @property
    def sqlite_path(self) -> str:
        """The filesystem path backing ``database_url`` (sqlite:/// only)."""
        prefix = "sqlite:///"
        if not self.database_url.startswith(prefix):
            raise ValueError("Only sqlite:/// database URLs are supported in Phase 1.")
        return self.database_url[len(prefix) :]


@lru_cache
def get_settings() -> Settings:
    return Settings()
