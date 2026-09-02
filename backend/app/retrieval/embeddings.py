"""Embedding provider abstraction.

`EmbeddingProvider` is the interface `DenseRetriever`/index-building code
depends on; `BGEEmbeddingProvider` is the only production implementation
(BAAI/bge-small-en-v1.5, the Phase 2 baseline model). Test doubles
(deterministic fake embeddings, no model download) live in
`tests/retrieval/fakes.py` — production code never imports a fake.

The model is loaded **once** per `BGEEmbeddingProvider` instance and reused
for every subsequent `embed_documents`/`embed_query` call — callers are
responsible for constructing one instance and holding onto it (e.g. as a
FastAPI dependency singleton), not constructing a fresh provider per
request.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

import numpy as np

from app.retrieval.errors import EmbeddingModelError

if TYPE_CHECKING:
    from sentence_transformers import SentenceTransformer


class EmbeddingProvider(ABC):
    """Batch document embedding + single query embedding.

    Implementations must:
    - return `float32` arrays shaped `(n, dimension)` / `(dimension,)`
    - be explicit about `dimension` and about whether vectors are
      L2-normalized (see `normalizes_embeddings`)
    - be deterministic: the same text always produces the same vector for a
      given model/revision (no dropout/sampling at inference time)
    """

    @property
    @abstractmethod
    def model_id(self) -> str: ...

    @property
    @abstractmethod
    def dimension(self) -> int: ...

    @property
    @abstractmethod
    def normalizes_embeddings(self) -> bool:
        """Whether returned vectors are L2-normalized (unit length).

        BGE's recommended usage pairs normalized embeddings with an inner
        product / cosine similarity metric — see `faiss_index.py`.
        """

    @abstractmethod
    def embed_documents(self, texts: list[str]) -> np.ndarray: ...

    @abstractmethod
    def embed_query(self, text: str) -> np.ndarray: ...


class BGEEmbeddingProvider(EmbeddingProvider):
    """`BAAI/bge-small-en-v1.5` via `sentence-transformers`.

    - Dimension: 384 (BGE-small's fixed output size).
    - Metric: cosine similarity, implemented as inner product over
      L2-normalized vectors (`normalize_embeddings=True` at encode time) —
      matches `faiss.IndexFlatIP` in `faiss_index.py`.
    - Model revision: not pinned to a specific commit hash here — the
      Hugging Face `main` revision of `BAAI/bge-small-en-v1.5` is used as
      published. See docs/research/reproducibility.md for why an exact
      revision pin was not practical to add in this environment (no local
      mirror/lockfile mechanism for HF revisions was already in place).
    - CPU-compatible; opportunistically uses a GPU if `sentence-transformers`
      detects one, but Phase 2 does not require it.
    """

    _DIMENSION = 384

    def __init__(self, model_name: str, batch_size: int = 32) -> None:
        self._model_name = model_name
        self._batch_size = batch_size
        self._model: SentenceTransformer | None = None  # lazy-loaded, then cached

    def _ensure_loaded(self) -> None:
        if self._model is not None:
            return
        try:
            from sentence_transformers import SentenceTransformer

            self._model = SentenceTransformer(self._model_name)
        except Exception as exc:  # noqa: BLE001 - surfaced as a domain error
            raise EmbeddingModelError(
                f"Failed to load embedding model '{self._model_name}': {exc}"
            ) from exc

    @property
    def model_id(self) -> str:
        return self._model_name

    @property
    def dimension(self) -> int:
        return self._DIMENSION

    @property
    def normalizes_embeddings(self) -> bool:
        return True

    def embed_documents(self, texts: list[str]) -> np.ndarray:
        self._ensure_loaded()
        assert self._model is not None
        try:
            vectors = self._model.encode(
                texts,
                batch_size=self._batch_size,
                normalize_embeddings=True,
                convert_to_numpy=True,
                show_progress_bar=False,
            )
        except Exception as exc:  # noqa: BLE001
            raise EmbeddingModelError(f"Embedding model failed to encode documents: {exc}") from exc
        return np.asarray(vectors, dtype=np.float32)

    def embed_query(self, text: str) -> np.ndarray:
        return self.embed_documents([text])[0]
