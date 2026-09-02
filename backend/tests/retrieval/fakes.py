"""Deterministic test doubles for retrieval components that would otherwise
require downloading real model weights (BGE, cross-encoder, an LLM for
HyDE). Used by the main (non-integration) test suite so CI never needs
network access or GPU/CPU-heavy model inference.
"""

from __future__ import annotations

import hashlib

import numpy as np

from app.retrieval.embeddings import EmbeddingProvider
from app.retrieval.interfaces import ExpansionResult, QueryExpander

FAKE_DIMENSION = 16


def _deterministic_vector(text: str, dimension: int = FAKE_DIMENSION) -> np.ndarray:
    """A reproducible pseudo-embedding: seed a small RNG from a hash of the
    text so the same text always yields the same vector, and different text
    (almost always) yields a different one, without loading any real model.
    """
    seed = int.from_bytes(hashlib.sha256(text.encode("utf-8")).digest()[:8], "big")
    rng = np.random.default_rng(seed)
    vector = rng.normal(size=dimension).astype(np.float32)
    norm = np.linalg.norm(vector)
    return vector / norm if norm > 0 else vector


class FakeEmbeddingProvider(EmbeddingProvider):
    """Hash-seeded deterministic embeddings; no model download."""

    def __init__(self, dimension: int = FAKE_DIMENSION) -> None:
        self._dimension = dimension

    @property
    def model_id(self) -> str:
        return "fake-embedding-provider"

    @property
    def dimension(self) -> int:
        return self._dimension

    @property
    def normalizes_embeddings(self) -> bool:
        return True

    def embed_documents(self, texts: list[str]) -> np.ndarray:
        return np.stack([_deterministic_vector(t, self._dimension) for t in texts])

    def embed_query(self, text: str) -> np.ndarray:
        return _deterministic_vector(text, self._dimension)


class FakeQueryExpander(QueryExpander):
    """Mocked HyDE provider — returns a canned/derived passage, no LLM call."""

    def __init__(self, available: bool = True, hypothetical_text: str | None = None) -> None:
        self._available = available
        self._hypothetical_text = hypothetical_text

    def is_available(self) -> bool:
        return self._available

    def expand(self, query: str) -> ExpansionResult:
        from app.retrieval.errors import HyDEUnavailableError

        if not self._available:
            raise HyDEUnavailableError("Fake HyDE provider is configured as unavailable.")
        text = self._hypothetical_text or f"A hypothetical passage answering: {query}"
        return ExpansionResult(
            original_query=query,
            expanded_text=text,
            model="fake-hyde-model",
            generation_params={"temperature": 0.0},
        )
