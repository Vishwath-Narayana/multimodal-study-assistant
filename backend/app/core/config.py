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

    llm_provider: str = "ollama"
    llm_model: str = ""

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
