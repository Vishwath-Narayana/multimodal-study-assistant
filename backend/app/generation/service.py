"""GenerationService: orchestrates the Phase 3 pipeline.

Mirrors `app.retrieval.service.RetrievalService`'s style: this class
coordinates the sufficiency checker, generator, citation validator,
attributor, token grounder, claim splitter, and contradiction checker — it
does not implement any of those algorithms itself. Every stage is toggle-
able via `GenerationServiceConfig` so ablation experiments (spec section 21)
can compare pipeline variants without duplicating this orchestration logic.

Consumes `list[RetrievalResult]` exactly as produced by
`RetrievalService.retrieve(...)` (Phase 2) — this module does not call
retrieval itself; the caller (the API layer, or an experiment script) is
responsible for retrieving evidence first and passing it in.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass

from app.generation.errors import EmptyQueryError
from app.generation.interfaces import (
    ChunkAttributor,
    CitationValidator,
    ClaimSplitter,
    ContradictionChecker,
    EvidenceSufficiencyChecker,
    Generator,
    TokenGrounder,
)
from app.generation.models import (
    AttributionScore,
    Citation,
    ClaimGrounding,
    ContradictionResult,
    GenerationResponse,
    GenerationTimingBreakdown,
    GenerationTrace,
    GroundingResult,
    SufficiencyResult,
)
from app.retrieval.llm_client import GenerationParams
from app.retrieval.models import RetrievalResult

_ABSTENTION_ANSWER = (
    "I couldn't find enough information in your uploaded study material to "
    "answer this reliably."
)


def _ms_since(start: float) -> float:
    return (time.perf_counter() - start) * 1000.0


@dataclass
class GenerationServiceConfig:
    max_tokens: int
    temperature: float

    # Ablation toggles (spec section 21) — each defaults to True so the
    # full pipeline runs unless a caller/experiment explicitly disables a
    # stage.
    enable_sufficiency_check: bool = True
    enable_citation_validation: bool = True
    enable_attribution: bool = True
    enable_token_grounding: bool = True
    enable_claim_grounding: bool = True
    enable_contradiction_check: bool = True


class GenerationService:
    def __init__(
        self,
        generator: Generator,
        sufficiency_checker: EvidenceSufficiencyChecker,
        citation_validator: CitationValidator,
        attributor: ChunkAttributor,
        token_grounder: TokenGrounder,
        claim_splitter: ClaimSplitter,
        contradiction_checker: ContradictionChecker,
        config: GenerationServiceConfig,
    ) -> None:
        self._generator = generator
        self._sufficiency_checker = sufficiency_checker
        self._citation_validator = citation_validator
        self._attributor = attributor
        self._token_grounder = token_grounder
        self._claim_splitter = claim_splitter
        self._contradiction_checker = contradiction_checker
        self._config = config

    def answer(
        self,
        query: str,
        evidence: list[RetrievalResult],
        request_id: str | None = None,
        retrieval_ms: float | None = None,
    ) -> GenerationResponse:
        if not query or not query.strip():
            raise EmptyQueryError("Query must not be empty.")

        request_id = request_id or uuid.uuid4().hex
        timings = GenerationTimingBreakdown(retrieval_ms=retrieval_ms)
        total_start = time.perf_counter()

        if self._config.enable_sufficiency_check:
            start = time.perf_counter()
            sufficiency = self._sufficiency_checker.check(query, evidence)
            timings.sufficiency_ms = _ms_since(start)
        else:
            sufficiency = SufficiencyResult(
                sufficient=True, reason="Sufficiency check disabled by configuration.", signals={}
            )

        if not sufficiency.sufficient:
            timings.total_ms = _ms_since(total_start)
            trace = GenerationTrace(
                request_id=request_id,
                query=query,
                provider=self._generator.provider_id,
                model=self._generator.model_id,
                sufficiency=sufficiency,
                timings=timings,
            )
            return GenerationResponse(
                request_id=request_id,
                query=query,
                answer=_ABSTENTION_ANSWER,
                answerable=False,
                evidence=evidence,
                citations=[],
                attribution=[],
                grounding=None,
                contradictions=ContradictionResult(has_conflict=False, conflicts=[]),
                claim_groundings=[],
                sufficiency=sufficiency,
                trace=trace,
            )

        start = time.perf_counter()
        params = GenerationParams(
            max_tokens=self._config.max_tokens, temperature=self._config.temperature
        )
        generated = self._generator.generate(query, evidence, params)
        timings.generation_ms = _ms_since(start)

        citations: list[Citation] = []
        if self._config.enable_citation_validation:
            start = time.perf_counter()
            citations = self._citation_validator.validate(generated.raw_chunk_ids, evidence)
            timings.citation_validation_ms = _ms_since(start)

        attribution: list[AttributionScore] = []
        if self._config.enable_attribution:
            start = time.perf_counter()
            attribution = self._attributor.attribute(generated.text, evidence)
            timings.attribution_ms = _ms_since(start)

        grounding: GroundingResult | None = None
        if self._config.enable_token_grounding:
            start = time.perf_counter()
            grounding = self._token_grounder.ground(generated.text, evidence)
            timings.grounding_ms = _ms_since(start)

        claim_groundings: list[ClaimGrounding] = []
        if self._config.enable_claim_grounding:
            claim_groundings = self._claim_splitter.split_and_attribute(
                generated.text, evidence, citations
            )

        contradictions = ContradictionResult(has_conflict=False, conflicts=[])
        if self._config.enable_contradiction_check:
            start = time.perf_counter()
            contradictions = self._contradiction_checker.check(evidence)
            timings.contradiction_ms = _ms_since(start)

        timings.total_ms = _ms_since(total_start)

        trace = GenerationTrace(
            request_id=request_id,
            query=query,
            provider=self._generator.provider_id,
            model=self._generator.model_id,
            sufficiency=sufficiency,
            citations=citations,
            attribution=attribution,
            grounding=grounding,
            contradictions=contradictions,
            claim_groundings=claim_groundings,
            prompt_char_count=None,
            output_char_count=len(generated.text),
            timings=timings,
        )

        return GenerationResponse(
            request_id=request_id,
            query=query,
            answer=generated.text,
            answerable=True,
            evidence=evidence,
            citations=citations,
            attribution=attribution,
            grounding=grounding,
            contradictions=contradictions,
            claim_groundings=claim_groundings,
            sufficiency=sufficiency,
            trace=trace,
        )
