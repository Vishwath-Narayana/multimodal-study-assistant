"""Deterministic test doubles for Study Engine components, so the default
test suite never needs a reachable Ollama server or a real model. Mirrors
`tests/generation/fakes.py`'s style."""

from __future__ import annotations

from app.retrieval.llm_client import GenerationParams
from app.retrieval.models import RetrievalResult
from app.study.errors import GenerationFailedError, ProviderUnavailableError
from app.study.interfaces import StudyGenerator
from app.study.models import Difficulty, ExplanationStyle, QuestionType, SummaryLength


class FakeStudyGenerator(StudyGenerator):
    """Returns a canned response per mode, ignoring the actual evidence/
    query — tests set `*_text` to whatever raw output shape they need to
    exercise (well-formed JSON, malformed JSON, missing fields, ...)."""

    def __init__(
        self,
        summary_text: str = "A fake summary. [chunk:c1]",
        explanation_text: str = "A fake explanation. [chunk:c1]",
        comparison_text: str | None = None,
        quiz_text: str | None = None,
        mcq_text: str | None = None,
        flashcards_text: str | None = None,
        unavailable: bool = False,
        fails: bool = False,
        provider: str = "fake",
        model: str = "fake-model",
    ) -> None:
        self._summary_text = summary_text
        self._explanation_text = explanation_text
        self._comparison_text = comparison_text or _DEFAULT_COMPARISON_JSON
        self._quiz_text = quiz_text or _DEFAULT_QUIZ_JSON
        self._mcq_text = mcq_text or _DEFAULT_MCQ_JSON
        self._flashcards_text = flashcards_text or _DEFAULT_FLASHCARDS_JSON
        self._unavailable = unavailable
        self._fails = fails
        self._provider = provider
        self._model = model

    @property
    def provider_id(self) -> str:
        return self._provider

    @property
    def model_id(self) -> str:
        return self._model

    def _check(self) -> None:
        if self._unavailable:
            raise ProviderUnavailableError("Fake provider is configured as unavailable.")
        if self._fails:
            raise GenerationFailedError("Fake provider is configured to fail generation.")

    def generate_summary(
        self,
        query: str,
        evidence: list[RetrievalResult],
        length: SummaryLength,
        params: GenerationParams,
    ) -> str:
        self._check()
        return self._summary_text

    def generate_explanation(
        self,
        query: str,
        evidence: list[RetrievalResult],
        style: ExplanationStyle,
        params: GenerationParams,
    ) -> str:
        self._check()
        return self._explanation_text

    def generate_comparison(
        self,
        topic_a: str,
        topic_b: str,
        evidence: list[RetrievalResult],
        params: GenerationParams,
    ) -> str:
        self._check()
        return self._comparison_text

    def generate_quiz(
        self,
        query: str,
        evidence: list[RetrievalResult],
        count: int,
        difficulty: Difficulty,
        question_type: QuestionType | None,
        params: GenerationParams,
    ) -> str:
        self._check()
        return self._quiz_text

    def generate_mcqs(
        self,
        query: str,
        evidence: list[RetrievalResult],
        count: int,
        difficulty: Difficulty,
        params: GenerationParams,
    ) -> str:
        self._check()
        return self._mcq_text

    def generate_flashcards(
        self,
        query: str,
        evidence: list[RetrievalResult],
        count: int,
        difficulty: Difficulty,
        params: GenerationParams,
    ) -> str:
        self._check()
        return self._flashcards_text


_DEFAULT_COMPARISON_JSON = """{
  "aspects": [
    {
      "aspect": "definition",
      "topic_a": "Topic A is defined in the evidence. [chunk:c1]",
      "topic_b": "Topic B is defined in the evidence. [chunk:c2]",
      "citations": ["c1", "c2"]
    }
  ]
}"""

_DEFAULT_QUIZ_JSON = """{
  "questions": [
    {
      "question": "What is BM25?",
      "answer": "A lexical ranking function.",
      "explanation": "Explained in the evidence.",
      "citations": ["c1"]
    }
  ]
}"""

_DEFAULT_MCQ_JSON = """{
  "items": [
    {
      "question": "What is BM25?",
      "options": [
        {"id": "A", "text": "A lexical ranking function"},
        {"id": "B", "text": "A neural network"},
        {"id": "C", "text": "A database"},
        {"id": "D", "text": "A compression algorithm"}
      ],
      "correct_option": "A",
      "explanation": "Explained in the evidence.",
      "citations": ["c1"]
    }
  ]
}"""

_DEFAULT_FLASHCARDS_JSON = """{
  "cards": [
    {
      "front": "What is BM25?",
      "back": "A lexical ranking function.",
      "explanation": "Explained in the evidence.",
      "citations": ["c1"]
    }
  ]
}"""
