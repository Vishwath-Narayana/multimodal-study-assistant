"""Abstract interfaces retrieval components implement.

Per the Phase 2 spec ("Interfaces: adapters around libraries, downstream
code must not depend on rank_bm25/FAISS directly") — `RetrievalService` and
`HybridRetriever` depend only on these protocols/ABCs, never on
`rank_bm25.BM25Okapi`, `faiss.Index`, or `sentence_transformers.*` directly.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from app.retrieval.models import RetrievalCandidate


@dataclass
class FusedCandidate:
    """One chunk's fused ranking, with per-source rank/score preserved.

    `source_ranks`/`source_scores` map source label ("bm25"/"dense") to that
    source's rank/score for this chunk, when it appeared in that list.
    """

    chunk_id: str
    document_id: str
    content: str
    fused_score: float
    rank: int
    page: int | None = None
    section: str | None = None
    parent_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    source_ranks: dict[str, int] = field(default_factory=dict)
    source_scores: dict[str, float] = field(default_factory=dict)


@dataclass
class RerankedCandidate:
    """One chunk after cross-encoder rescoring, with fusion info preserved."""

    chunk_id: str
    document_id: str
    content: str
    rerank_score: float
    rank: int
    page: int | None = None
    section: str | None = None
    parent_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    fused_score: float | None = None
    source_ranks: dict[str, int] = field(default_factory=dict)
    source_scores: dict[str, float] = field(default_factory=dict)


@dataclass
class ExpansionResult:
    """Output of a `QueryExpander` (HyDE): the generated text plus provenance."""

    original_query: str
    expanded_text: str
    model: str
    generation_params: dict[str, Any] = field(default_factory=dict)


class Retriever(ABC):
    """A single retrieval strategy over the indexed chunk corpus."""

    @abstractmethod
    def retrieve(self, query: str, top_k: int) -> list[RetrievalCandidate]:
        """Return up to `top_k` candidates ranked best-first (rank starts at 1)."""


class FusionStrategy(ABC):
    """Combines multiple ranked candidate lists into one ranked list."""

    @abstractmethod
    def fuse(self, ranked_lists: dict[str, list[RetrievalCandidate]]) -> list[FusedCandidate]:
        """`ranked_lists` maps a source label (e.g. "bm25", "dense") to its
        ranked candidates. Returns a deduped, fused ranking."""


class QueryExpander(ABC):
    """Expands a user query into auxiliary text used by another retriever.

    Phase 2's only expander is HyDE: it never receives retrieved document
    content, only the user's own query (see docs/research/security.md).
    """

    @abstractmethod
    def expand(self, query: str) -> ExpansionResult:
        """Raise `app.retrieval.errors.HyDEUnavailableError` if the backend
        is unreachable — never silently return the original query."""

    @abstractmethod
    def is_available(self) -> bool:
        """Cheap reachability check, used for degraded-mode decisions."""


class Reranker(ABC):
    """Rescoring a candidate pool against the original query."""

    @abstractmethod
    def rerank(
        self, query: str, candidates: list[FusedCandidate], top_k: int
    ) -> list[RerankedCandidate]:
        """Return up to `top_k` candidates, best-first."""
