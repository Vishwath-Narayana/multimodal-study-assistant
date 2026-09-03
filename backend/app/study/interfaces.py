"""Abstract interfaces for the Phase 5 Study Engine.

Mirrors `app.generation.interfaces`: `StudyEngineService` (see `service.py`)
depends only on this ABC, never on a concrete LLM SDK. Per ADR-004, model
implementations must be swappable without rewriting the orchestration
layer. One `Generator`-shaped ABC covers every study mode (rather than six
separate ABCs) because every mode shares the same evidence-in/text-out
shape and the same provider/model identity — only the prompt differs per
mode, which lives in `app.study.prompts`, not on this interface.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from app.retrieval.llm_client import GenerationParams
from app.retrieval.models import RetrievalResult
from app.study.models import Difficulty, ExplanationStyle, QuestionType, SummaryLength


class StudyGenerator(ABC):
    """Produces raw LLM text for one study mode from a fixed evidence set.

    Like `app.generation.interfaces.Generator`, an implementation must not
    perform its own retrieval or allow the underlying LLM to fetch
    additional context — the evidence set is exactly what the caller
    retrieved for this request.
    """

    @abstractmethod
    def generate_summary(
        self,
        query: str,
        evidence: list[RetrievalResult],
        length: SummaryLength,
        params: GenerationParams,
    ) -> str: ...

    @abstractmethod
    def generate_explanation(
        self,
        query: str,
        evidence: list[RetrievalResult],
        style: ExplanationStyle,
        params: GenerationParams,
    ) -> str: ...

    @abstractmethod
    def generate_comparison(
        self,
        topic_a: str,
        topic_b: str,
        evidence: list[RetrievalResult],
        params: GenerationParams,
    ) -> str: ...

    @abstractmethod
    def generate_quiz(
        self,
        query: str,
        evidence: list[RetrievalResult],
        count: int,
        difficulty: Difficulty,
        question_type: QuestionType | None,
        params: GenerationParams,
    ) -> str: ...

    @abstractmethod
    def generate_mcqs(
        self,
        query: str,
        evidence: list[RetrievalResult],
        count: int,
        difficulty: Difficulty,
        params: GenerationParams,
    ) -> str: ...

    @abstractmethod
    def generate_flashcards(
        self,
        query: str,
        evidence: list[RetrievalResult],
        count: int,
        difficulty: Difficulty,
        params: GenerationParams,
    ) -> str: ...

    @property
    @abstractmethod
    def provider_id(self) -> str: ...

    @property
    @abstractmethod
    def model_id(self) -> str: ...
