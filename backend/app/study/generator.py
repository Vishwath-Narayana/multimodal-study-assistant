"""`StudyGenerator` implementation.

`OllamaStudyGenerator` reuses `app.retrieval.llm_client.LLMClient` exactly
as `app.generation.generator.OllamaGenerator` does (per ADR-005: no second
HTTP client) — it only adds study-mode-specific prompt selection on top.
Nothing here is exercised by the default test suite (see
`tests/study/fakes.py::FakeStudyGenerator`) or by CI — real generation
requires a reachable Ollama server with the model already pulled.
"""

from __future__ import annotations

import httpx

from app.retrieval.llm_client import GenerationParams, LLMClient
from app.retrieval.models import RetrievalResult
from app.study.errors import GenerationFailedError, ProviderUnavailableError
from app.study.interfaces import StudyGenerator
from app.study.models import Difficulty, ExplanationStyle, QuestionType, SummaryLength
from app.study.prompts import (
    render_comparison_prompt,
    render_explanation_prompt,
    render_flashcards_prompt,
    render_mcq_prompt,
    render_quiz_prompt,
    render_summary_prompt,
)


class OllamaStudyGenerator(StudyGenerator):
    def __init__(self, client: LLMClient) -> None:
        self._client = client

    @property
    def provider_id(self) -> str:
        return "ollama"

    @property
    def model_id(self) -> str:
        return self._client.model_id

    def _generate(self, prompt: str, params: GenerationParams) -> str:
        if not self._client.is_reachable():
            raise ProviderUnavailableError(
                f"LLM provider '{self.provider_id}' (model '{self.model_id}') is unreachable. "
                "Is Ollama running and is the model pulled?"
            )
        try:
            return self._client.generate(prompt, params)
        except httpx.HTTPError as exc:
            raise GenerationFailedError(f"Generation request failed: {exc}") from exc

    def generate_summary(
        self,
        query: str,
        evidence: list[RetrievalResult],
        length: SummaryLength,
        params: GenerationParams,
    ) -> str:
        return self._generate(render_summary_prompt(query, evidence, length), params)

    def generate_explanation(
        self,
        query: str,
        evidence: list[RetrievalResult],
        style: ExplanationStyle,
        params: GenerationParams,
    ) -> str:
        return self._generate(render_explanation_prompt(query, evidence, style), params)

    def generate_comparison(
        self,
        topic_a: str,
        topic_b: str,
        evidence: list[RetrievalResult],
        params: GenerationParams,
    ) -> str:
        return self._generate(render_comparison_prompt(topic_a, topic_b, evidence), params)

    def generate_quiz(
        self,
        query: str,
        evidence: list[RetrievalResult],
        count: int,
        difficulty: Difficulty,
        question_type: QuestionType | None,
        params: GenerationParams,
    ) -> str:
        prompt = render_quiz_prompt(query, evidence, count, difficulty, question_type)
        return self._generate(prompt, params)

    def generate_mcqs(
        self,
        query: str,
        evidence: list[RetrievalResult],
        count: int,
        difficulty: Difficulty,
        params: GenerationParams,
    ) -> str:
        return self._generate(render_mcq_prompt(query, evidence, count, difficulty), params)

    def generate_flashcards(
        self,
        query: str,
        evidence: list[RetrievalResult],
        count: int,
        difficulty: Difficulty,
        params: GenerationParams,
    ) -> str:
        return self._generate(render_flashcards_prompt(query, evidence, count, difficulty), params)
