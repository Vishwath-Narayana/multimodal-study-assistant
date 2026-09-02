"""Abstract interfaces for the Phase 3 generation/explainability pipeline.

Mirrors `app.retrieval.interfaces`: `GenerationService` (see `service.py`)
depends only on these ABCs, never on a concrete LLM SDK or a specific
grounding/attribution algorithm directly. Per ADR-004, model
implementations must be swappable without rewriting the orchestration
layer.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from app.generation.models import (
    AttributionScore,
    Citation,
    ClaimGrounding,
    ContradictionResult,
    GeneratedAnswer,
    GroundingResult,
    SufficiencyResult,
)
from app.retrieval.llm_client import GenerationParams
from app.retrieval.models import RetrievalResult


class Generator(ABC):
    """Produces a grounded answer from a query and a fixed evidence set.

    The evidence set is exactly the caller's retrieved chunks — a
    `Generator` implementation must not perform its own retrieval or allow
    the underlying LLM to fetch additional context (spec: "The LLM should
    NOT be allowed to arbitrarily retrieve more data").
    """

    @abstractmethod
    def generate(
        self, query: str, evidence: list[RetrievalResult], params: GenerationParams
    ) -> GeneratedAnswer: ...

    @property
    @abstractmethod
    def provider_id(self) -> str: ...

    @property
    @abstractmethod
    def model_id(self) -> str: ...


class EvidenceSufficiencyChecker(ABC):
    """Decides whether retrieved evidence is sufficient to attempt an answer."""

    @abstractmethod
    def check(self, query: str, evidence: list[RetrievalResult]) -> SufficiencyResult: ...


class CitationValidator(ABC):
    """Validates chunk_ids a `Generator` claims to cite against the
    evidence set that was actually retrieved for this request."""

    @abstractmethod
    def validate(
        self, raw_chunk_ids: list[str], evidence: list[RetrievalResult]
    ) -> list[Citation]: ...


class ChunkAttributor(ABC):
    """Scores how strongly each retrieved chunk supports the answer."""

    @abstractmethod
    def attribute(
        self, answer: str, evidence: list[RetrievalResult]
    ) -> list[AttributionScore]: ...


class TokenGrounder(ABC):
    """Deterministic token/phrase grounding of the answer against evidence."""

    @abstractmethod
    def ground(self, answer: str, evidence: list[RetrievalResult]) -> GroundingResult: ...


class ClaimSplitter(ABC):
    """Splits an answer into claims and attributes each to supporting chunks."""

    @abstractmethod
    def split_and_attribute(
        self, answer: str, evidence: list[RetrievalResult], citations: list[Citation]
    ) -> list[ClaimGrounding]: ...


class ContradictionChecker(ABC):
    """Detects likely disagreement between retrieved evidence chunks."""

    @abstractmethod
    def check(self, evidence: list[RetrievalResult]) -> ContradictionResult: ...
