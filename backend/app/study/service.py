"""StudyEngineService: orchestrates the Phase 5 Study Engine pipeline.

Mirrors `app.generation.service.GenerationService`'s style: this class
coordinates the sufficiency checker, the `StudyGenerator`, output parsing,
citation validation, and the contradiction checker — it does not implement
any retrieval itself (spec section 4: "The Study Engine should NOT directly
implement its own retrieval"). Exactly like `GenerationService`, the caller
(the API layer) is responsible for retrieving evidence first via
`RetrievalService` and passing it in.

RETRIEVE -> GROUND -> GENERATE -> VALIDATE -> ATTRIBUTE (spec section 41),
per mode:

    evidence
      -> sufficiency check (reuse app.generation.sufficiency)
      -> StudyGenerator.generate_* (mode-specific prompt, raw text out)
      -> app.study.parsing (structured modes only)
      -> app.study.validation (business rules + citation validation, reuse
         app.generation.citations.DeterministicCitationValidator)
      -> app.study.duplicates (within-batch dedup)
      -> StudyResponse
"""

from __future__ import annotations

import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from app.generation.citations import extract_citations, strip_citation_markers
from app.generation.interfaces import (
    CitationValidator,
    ContradictionChecker,
    EvidenceSufficiencyChecker,
)
from app.generation.models import ContradictionResult, SufficiencyResult
from app.retrieval.llm_client import GenerationParams
from app.retrieval.models import RetrievalResult
from app.study.errors import EmptyQueryError, InvalidRequestError
from app.study.interfaces import StudyGenerator
from app.study.models import (
    ComparisonItem,
    Difficulty,
    ExplanationItem,
    ExplanationStyle,
    QuestionType,
    StudyGenerationStats,
    StudyMode,
    StudyResponse,
    StudyTimingBreakdown,
    StudyTrace,
    SummaryItem,
    SummaryLength,
)
from app.study.parsing import parse_comparison, parse_flashcards, parse_mcqs, parse_quiz
from app.study.validation import (
    ValidationOutcome,
    validate_comparison_aspects,
    validate_flashcards,
    validate_mcq_items,
    validate_quiz_questions,
)


def _ms_since(start: float) -> float:
    return (time.perf_counter() - start) * 1000.0


_NO_EVIDENCE_SUFFICIENCY = SufficiencyResult(
    sufficient=True, reason="Sufficiency check disabled by configuration.", signals={}
)
_NO_CONTRADICTIONS = ContradictionResult(has_conflict=False, conflicts=[])


@dataclass
class StudyEngineServiceConfig:
    max_tokens: int
    temperature: float
    min_count: int
    max_count: int

    # Ablation toggles (spec section 30), mirroring GenerationServiceConfig.
    enable_sufficiency_check: bool = True
    enable_citation_validation: bool = True
    enable_contradiction_check: bool = True


class StudyEngineService:
    def __init__(
        self,
        generator: StudyGenerator,
        sufficiency_checker: EvidenceSufficiencyChecker,
        citation_validator: CitationValidator,
        contradiction_checker: ContradictionChecker,
        config: StudyEngineServiceConfig,
    ) -> None:
        self._generator = generator
        self._sufficiency_checker = sufficiency_checker
        self._citation_validator = citation_validator
        self._contradiction_checker = contradiction_checker
        self._config = config

    # -- shared helpers -----------------------------------------------

    def _check_count(self, count: int) -> None:
        if not (self._config.min_count <= count <= self._config.max_count):
            raise InvalidRequestError(
                f"Requested count {count} is outside the allowed range "
                f"[{self._config.min_count}, {self._config.max_count}]."
            )

    def _check_sufficiency(
        self, query: str, evidence: list[RetrievalResult], timings: StudyTimingBreakdown
    ) -> SufficiencyResult:
        if not self._config.enable_sufficiency_check:
            return _NO_EVIDENCE_SUFFICIENCY
        start = time.perf_counter()
        result = self._sufficiency_checker.check(query, evidence)
        timings.sufficiency_ms = _ms_since(start)
        return result

    def _check_contradictions(self, evidence: list[RetrievalResult]) -> ContradictionResult:
        """Per-stage timing is not separately tracked for this check — its
        cost is folded into `StudyTimingBreakdown.total_ms`, same as
        `GenerationService` does for every other stage it times
        individually; this one is cheap enough not to warrant its own
        field."""
        if not self._config.enable_contradiction_check:
            return _NO_CONTRADICTIONS
        return self._contradiction_checker.check(evidence)

    def _params(self) -> GenerationParams:
        return GenerationParams(
            max_tokens=self._config.max_tokens, temperature=self._config.temperature
        )

    def _abstain(
        self,
        mode: StudyMode,
        query: str,
        evidence: list[RetrievalResult],
        sufficiency: SufficiencyResult,
        request_id: str,
        timings: StudyTimingBreakdown,
        total_start: float,
    ) -> StudyResponse:
        timings.total_ms = _ms_since(total_start)
        trace = StudyTrace(
            request_id=request_id,
            mode=mode,
            query=query,
            provider=self._generator.provider_id,
            model=self._generator.model_id,
            sufficiency=sufficiency,
            timings=timings,
        )
        return StudyResponse(
            request_id=request_id,
            mode=mode,
            query=query,
            answerable=False,
            reason=sufficiency.reason,
            evidence=evidence,
            items=[],
            contradictions=_NO_CONTRADICTIONS,
            sufficiency=sufficiency,
            trace=trace,
        )

    # -- unstructured modes ---------------------------------------------

    def summarize(
        self,
        query: str,
        evidence: list[RetrievalResult],
        length: SummaryLength = SummaryLength.STANDARD,
        request_id: str | None = None,
        retrieval_ms: float | None = None,
    ) -> StudyResponse:
        return self._run_unstructured_mode(
            StudyMode.SUMMARY,
            query,
            evidence,
            lambda ev, params: self._generator.generate_summary(query, ev, length, params),
            SummaryItem,
            request_id,
            retrieval_ms,
        )

    def explain(
        self,
        query: str,
        evidence: list[RetrievalResult],
        style: ExplanationStyle = ExplanationStyle.STANDARD,
        request_id: str | None = None,
        retrieval_ms: float | None = None,
    ) -> StudyResponse:
        return self._run_unstructured_mode(
            StudyMode.EXPLAIN,
            query,
            evidence,
            lambda ev, params: self._generator.generate_explanation(query, ev, style, params),
            ExplanationItem,
            request_id,
            retrieval_ms,
        )

    def _run_unstructured_mode(
        self,
        mode: StudyMode,
        query: str,
        evidence: list[RetrievalResult],
        generate: Callable[[list[RetrievalResult], GenerationParams], str],
        item_cls: type[SummaryItem] | type[ExplanationItem],
        request_id: str | None,
        retrieval_ms: float | None,
    ) -> StudyResponse:
        if not query or not query.strip():
            raise EmptyQueryError("Query must not be empty.")

        request_id = request_id or uuid.uuid4().hex
        timings = StudyTimingBreakdown(retrieval_ms=retrieval_ms)
        total_start = time.perf_counter()

        sufficiency = self._check_sufficiency(query, evidence, timings)
        if not sufficiency.sufficient:
            return self._abstain(
                mode, query, evidence, sufficiency, request_id, timings, total_start
            )

        start = time.perf_counter()
        text = generate(evidence, self._params())
        timings.generation_ms = _ms_since(start)

        raw_chunk_ids = extract_citations(text)
        citations = self._citation_validator.validate(raw_chunk_ids, evidence)
        content = strip_citation_markers(text).strip()
        valid_ids = [c.chunk_id for c in citations if c.valid]

        item = item_cls(content=content, citations=citations, source_chunk_ids=valid_ids)

        contradictions = self._check_contradictions(evidence)
        timings.total_ms = _ms_since(total_start)

        stats = StudyGenerationStats(
            requested_count=1, generated_count=1, validated_count=1, rejected_count=0
        )
        trace = StudyTrace(
            request_id=request_id,
            mode=mode,
            query=query,
            provider=self._generator.provider_id,
            model=self._generator.model_id,
            sufficiency=sufficiency,
            stats=stats,
            timings=timings,
        )
        return StudyResponse(
            request_id=request_id,
            mode=mode,
            query=query,
            answerable=True,
            reason=None,
            evidence=evidence,
            items=[item],
            contradictions=contradictions,
            sufficiency=sufficiency,
            trace=trace,
        )

    # -- comparison -------------------------------------------------------

    def compare(
        self,
        topic_a: str,
        topic_b: str,
        evidence_a: list[RetrievalResult],
        evidence_b: list[RetrievalResult],
        request_id: str | None = None,
        retrieval_ms: float | None = None,
    ) -> StudyResponse:
        if not topic_a or not topic_a.strip() or not topic_b or not topic_b.strip():
            raise EmptyQueryError("Both topics must be non-empty.")

        request_id = request_id or uuid.uuid4().hex
        timings = StudyTimingBreakdown(retrieval_ms=retrieval_ms)
        total_start = time.perf_counter()

        query = f"{topic_a} vs {topic_b}"
        sufficiency_a = self._check_sufficiency(topic_a, evidence_a, timings)
        sufficiency_b = self._check_sufficiency(topic_b, evidence_b, timings)

        combined_evidence: list[RetrievalResult] = []
        seen_chunk_ids: set[str] = set()
        for evidence_item in [*evidence_a, *evidence_b]:
            if evidence_item.chunk_id in seen_chunk_ids:
                continue
            seen_chunk_ids.add(evidence_item.chunk_id)
            combined_evidence.append(evidence_item)

        if not sufficiency_a.sufficient and not sufficiency_b.sufficient:
            combined_reason = (
                f"Insufficient evidence for both topics. {sufficiency_a.reason} "
                f"{sufficiency_b.reason}"
            )
            combined = SufficiencyResult(sufficient=False, reason=combined_reason, signals={})
            return self._abstain(
                StudyMode.COMPARE,
                query,
                combined_evidence,
                combined,
                request_id,
                timings,
                total_start,
            )

        start = time.perf_counter()
        text = self._generator.generate_comparison(
            topic_a, topic_b, combined_evidence, self._params()
        )
        timings.generation_ms = _ms_since(start)

        parse_start = time.perf_counter()
        raw_aspects = parse_comparison(text)
        timings.parsing_ms = _ms_since(parse_start)

        validate_start = time.perf_counter()
        aspects, outcome = validate_comparison_aspects(
            raw_aspects,
            combined_evidence,
            self._citation_validator,
            require_citations=self._config.enable_citation_validation,
        )
        timings.validation_ms = _ms_since(validate_start)

        incomplete_for = []
        if not sufficiency_a.sufficient:
            incomplete_for.append("topic_a")
        if not sufficiency_b.sufficient:
            incomplete_for.append("topic_b")

        item = ComparisonItem(
            topic_a=topic_a, topic_b=topic_b, aspects=aspects, incomplete_for=incomplete_for
        )

        contradictions = self._check_contradictions(combined_evidence)
        timings.total_ms = _ms_since(total_start)

        combined_sufficiency = SufficiencyResult(
            sufficient=True,
            reason=(
                "Evidence sufficient for at least one topic."
                if incomplete_for
                else "Evidence sufficient for both topics."
            ),
            signals={"incomplete_for": incomplete_for},
        )
        stats = StudyGenerationStats(
            requested_count=None,
            generated_count=outcome.generated_count,
            validated_count=outcome.validated_count,
            rejected_count=outcome.rejected_count,
            duplicate_count=outcome.duplicate_count,
        )
        trace = StudyTrace(
            request_id=request_id,
            mode=StudyMode.COMPARE,
            query=query,
            provider=self._generator.provider_id,
            model=self._generator.model_id,
            sufficiency=combined_sufficiency,
            stats=stats,
            timings=timings,
        )
        return StudyResponse(
            request_id=request_id,
            mode=StudyMode.COMPARE,
            query=query,
            answerable=True,
            reason=None,
            evidence=combined_evidence,
            items=[item],
            contradictions=contradictions,
            sufficiency=combined_sufficiency,
            trace=trace,
        )

    # -- quiz / mcq / flashcards ------------------------------------------

    def generate_quiz(
        self,
        query: str,
        evidence: list[RetrievalResult],
        count: int = 5,
        difficulty: Difficulty = Difficulty.MEDIUM,
        question_type: QuestionType = QuestionType.CONCEPTUAL,
        request_id: str | None = None,
        retrieval_ms: float | None = None,
    ) -> StudyResponse:
        self._check_count(count)
        return self._run_structured_mode(
            StudyMode.QUIZ,
            query,
            evidence,
            request_id,
            retrieval_ms,
            generate=lambda ev, params: self._generator.generate_quiz(
                query, ev, count, difficulty, question_type, params
            ),
            parse=parse_quiz,
            validate=lambda raw, ev: validate_quiz_questions(
                raw,
                ev,
                self._citation_validator,
                difficulty,
                question_type,
                require_citations=self._config.enable_citation_validation,
            ),
            requested_count=count,
        )

    def generate_mcqs(
        self,
        query: str,
        evidence: list[RetrievalResult],
        count: int = 5,
        difficulty: Difficulty = Difficulty.MEDIUM,
        request_id: str | None = None,
        retrieval_ms: float | None = None,
    ) -> StudyResponse:
        self._check_count(count)
        return self._run_structured_mode(
            StudyMode.MCQ,
            query,
            evidence,
            request_id,
            retrieval_ms,
            generate=lambda ev, params: self._generator.generate_mcqs(
                query, ev, count, difficulty, params
            ),
            parse=parse_mcqs,
            validate=lambda raw, ev: validate_mcq_items(
                raw,
                ev,
                self._citation_validator,
                difficulty,
                require_citations=self._config.enable_citation_validation,
            ),
            requested_count=count,
        )

    def generate_flashcards(
        self,
        query: str,
        evidence: list[RetrievalResult],
        count: int = 5,
        difficulty: Difficulty = Difficulty.MEDIUM,
        request_id: str | None = None,
        retrieval_ms: float | None = None,
    ) -> StudyResponse:
        self._check_count(count)
        return self._run_structured_mode(
            StudyMode.FLASHCARDS,
            query,
            evidence,
            request_id,
            retrieval_ms,
            generate=lambda ev, params: self._generator.generate_flashcards(
                query, ev, count, difficulty, params
            ),
            parse=parse_flashcards,
            validate=lambda raw, ev: validate_flashcards(
                raw,
                ev,
                self._citation_validator,
                difficulty,
                require_citations=self._config.enable_citation_validation,
            ),
            requested_count=count,
        )

    def _run_structured_mode(
        self,
        mode: StudyMode,
        query: str,
        evidence: list[RetrievalResult],
        request_id: str | None,
        retrieval_ms: float | None,
        *,
        generate: Callable[[list[RetrievalResult], GenerationParams], str],
        parse: Callable[[str], list[Any]],
        validate: Callable[[list[Any], list[RetrievalResult]], tuple[list[Any], ValidationOutcome]],
        requested_count: int,
    ) -> StudyResponse:
        if not query or not query.strip():
            raise EmptyQueryError("Query must not be empty.")

        request_id = request_id or uuid.uuid4().hex
        timings = StudyTimingBreakdown(retrieval_ms=retrieval_ms)
        total_start = time.perf_counter()

        sufficiency = self._check_sufficiency(query, evidence, timings)
        if not sufficiency.sufficient:
            return self._abstain(
                mode, query, evidence, sufficiency, request_id, timings, total_start
            )

        start = time.perf_counter()
        text = generate(evidence, self._params())
        timings.generation_ms = _ms_since(start)

        parse_start = time.perf_counter()
        raw_items = parse(text)
        timings.parsing_ms = _ms_since(parse_start)

        validate_start = time.perf_counter()
        items, outcome = validate(raw_items, evidence)
        timings.validation_ms = _ms_since(validate_start)

        contradictions = self._check_contradictions(evidence)
        timings.total_ms = _ms_since(total_start)

        answerable = len(items) > 0
        reason = None if answerable else "No generated study items passed validation."

        stats = StudyGenerationStats(
            requested_count=requested_count,
            generated_count=outcome.generated_count,
            validated_count=outcome.validated_count,
            rejected_count=outcome.rejected_count,
            duplicate_count=outcome.duplicate_count,
        )
        trace = StudyTrace(
            request_id=request_id,
            mode=mode,
            query=query,
            provider=self._generator.provider_id,
            model=self._generator.model_id,
            sufficiency=sufficiency,
            stats=stats,
            timings=timings,
        )
        return StudyResponse(
            request_id=request_id,
            mode=mode,
            query=query,
            answerable=answerable,
            reason=reason,
            evidence=evidence,
            items=list(items),
            contradictions=contradictions,
            sufficiency=sufficiency,
            trace=trace,
        )
