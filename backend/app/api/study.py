"""Study Engine endpoints (Phase 5).

`POST /study/{summary,explain,compare,quiz,mcq,flashcards}`: retrieves
evidence via the existing Phase 2 `RetrievalService` (no retrieval logic is
reimplemented here — same pattern as `app.api.chat`), then runs it through
`StudyEngineService` (evidence sufficiency -> grounded study generation ->
structured-output parsing -> validation -> citation validation) and
returns one structured response per mode. Six endpoints rather than one
unified `/study/generate` (spec section 22) because each mode's request
shape genuinely differs (compare needs two topics, quiz/mcq/flashcards need
count/difficulty) — see `app.schemas.study`.

Document scoping (spec section 5, "optional source/document scope"):
`document_id` narrows evidence to chunks from one already-ingested
document, applied as a post-filter over the retrieved results (no
document-scoped retrieval mode exists yet — see
docs/architecture/study-engine.md "Limitations"), so a scoped request can
return fewer than `top_k` evidence items when the document doesn't appear
early in the ranked results.
"""

from __future__ import annotations

import logging
import sqlite3

from fastapi import APIRouter, Depends, HTTPException

from app.api.retrieval import _ERROR_STATUS as _RETRIEVAL_ERROR_STATUS
from app.api.retrieval import _get_connection, get_retrieval_service
from app.core.config import Settings, get_settings
from app.generation.citations import DeterministicCitationValidator
from app.generation.contradiction import ContradictionConfig, LexicalContradictionChecker
from app.generation.injection_detection import scan_evidence_for_injection_signals
from app.generation.models import Citation, ContradictionResult, SufficiencyResult
from app.generation.sufficiency import HeuristicSufficiencyChecker, SufficiencyConfig
from app.ingestion.repository import ChunkRepository, DocumentRepository
from app.retrieval.errors import RetrievalError
from app.retrieval.llm_client import OllamaClient
from app.retrieval.models import RetrievalResult
from app.retrieval.service import RetrievalService
from app.schemas.study import (
    CitationResponse,
    CompareRequest,
    CompareResponse,
    ComparisonAspectResponse,
    ComparisonItemResponse,
    ConflictResponse,
    ContradictionResponse,
    EvidenceItemResponse,
    ExplainRequest,
    ExplainResponse,
    FlashcardResponse,
    FlashcardsRequest,
    FlashcardsResponse,
    MCQItemResponse,
    MCQOptionResponse,
    MCQRequest,
    MCQResponse,
    QuizQuestionResponse,
    QuizRequest,
    QuizResponse,
    StudyStatsResponse,
    StudyTimingResponse,
    StudyTraceResponse,
    SufficiencyResponse,
    SummaryItemResponse,
    SummaryRequest,
    SummaryResponse,
    preview,
)
from app.study.errors import (
    EmptyQueryError,
    GenerationFailedError,
    InvalidRequestError,
    MalformedStudyOutputError,
    ProviderUnavailableError,
    StudyError,
)
from app.study.generator import OllamaStudyGenerator
from app.study.interfaces import StudyGenerator
from app.study.models import (
    ComparisonItem,
    Difficulty,
    ExplanationItem,
    ExplanationStyle,
    Flashcard,
    MCQItem,
    QuestionType,
    QuizQuestion,
    StudyResponse,
    SummaryItem,
    SummaryLength,
)
from app.study.repository import StudyItemRepository
from app.study.service import StudyEngineService, StudyEngineServiceConfig

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/study", tags=["study"])

# Same lifecycle discipline as app.api.chat: a heavy/long-lived client is
# cached per process, keyed by its configuration, with a test-only reset
# hook. Kept as its own cache/key (rather than reusing chat's) so a
# different `study_*` timeout setting doesn't invalidate the chat cache.
_study_generator_cache: dict[tuple[str, str], StudyGenerator] = {}


def reset_study_generator_cache() -> None:
    """Test-only hook, mirroring `app.api.chat.reset_generator_cache`."""
    _study_generator_cache.clear()


def get_study_generator(settings: Settings = Depends(get_settings)) -> StudyGenerator:
    key = (settings.llm_provider, settings.llm_model)
    generator = _study_generator_cache.get(key)
    if generator is None:
        if settings.llm_provider != "ollama":
            raise HTTPException(
                status_code=500,
                detail=f"Unsupported llm_provider '{settings.llm_provider}'.",
            )
        client = OllamaClient(
            settings.ollama_base_url, settings.llm_model, settings.study_timeout_seconds
        )
        generator = OllamaStudyGenerator(client)
        _study_generator_cache[key] = generator
    return generator


def get_study_engine_service(
    settings: Settings = Depends(get_settings),
    conn: sqlite3.Connection = Depends(_get_connection),
    generator: StudyGenerator = Depends(get_study_generator),
) -> StudyEngineService:
    known_chunk_ids = {c.id for c in ChunkRepository(conn).list_all()}

    sufficiency_checker = HeuristicSufficiencyChecker(
        SufficiencyConfig(
            min_chunks=settings.sufficiency_min_chunks,
            min_lexical_overlap=settings.sufficiency_min_lexical_overlap,
            min_reranker_score=settings.sufficiency_min_reranker_score,
        )
    )
    citation_validator = DeterministicCitationValidator(known_chunk_ids=known_chunk_ids)
    contradiction_checker = LexicalContradictionChecker(
        ContradictionConfig(topic_overlap_threshold=settings.contradiction_topic_overlap_threshold)
    )
    config = StudyEngineServiceConfig(
        max_tokens=settings.study_max_tokens,
        temperature=settings.study_temperature,
        min_count=settings.study_min_count,
        max_count=settings.study_max_count,
    )
    return StudyEngineService(
        generator=generator,
        sufficiency_checker=sufficiency_checker,
        citation_validator=citation_validator,
        contradiction_checker=contradiction_checker,
        config=config,
    )


_ERROR_STATUS: dict[type[StudyError], int] = {
    EmptyQueryError: 400,
    InvalidRequestError: 400,
    ProviderUnavailableError: 503,
    GenerationFailedError: 502,
    MalformedStudyOutputError: 502,
}


def _handle_retrieval_error(exc: RetrievalError) -> HTTPException:
    status_code = next(
        (
            code
            for error_type, code in _RETRIEVAL_ERROR_STATUS.items()
            if isinstance(exc, error_type)
        ),
        500,
    )
    return HTTPException(status_code=status_code, detail=exc.message)


def _handle_study_error(exc: StudyError) -> HTTPException:
    status_code = next(
        (code for error_type, code in _ERROR_STATUS.items() if isinstance(exc, error_type)), 500
    )
    return HTTPException(status_code=status_code, detail=exc.message)


def _scope_to_document(
    evidence: list[RetrievalResult], document_id: str | None
) -> list[RetrievalResult]:
    if document_id is None:
        return evidence
    return [item for item in evidence if item.document_id == document_id]


def _retrieve(
    retrieval_service: RetrievalService,
    query: str,
    mode: str,
    top_k: int,
    document_id: str | None,
) -> tuple[list[RetrievalResult], str, float | None]:
    try:
        evidence, trace = retrieval_service.retrieve(query, mode, top_k=top_k)
    except RetrievalError as exc:
        raise _handle_retrieval_error(exc) from exc
    scoped = _scope_to_document(evidence, document_id)
    evidence_pairs = [(item.chunk_id, item.content) for item in scoped]
    for signal in scan_evidence_for_injection_signals(evidence_pairs):
        logger.warning(
            "security.prompt_injection_signal request_id=%s chunk_id=%s "
            "matched_patterns=%s score=%.2f",
            trace.request_id,
            signal.chunk_id,
            ",".join(signal.matched_patterns),
            signal.score,
        )
    return scoped, trace.request_id, trace.timings.total_ms


def _build_evidence_items(
    evidence: list[RetrievalResult], document_repo: DocumentRepository
) -> list[EvidenceItemResponse]:
    filename_cache: dict[str, str | None] = {}

    def filename_for(document_id: str) -> str | None:
        if document_id not in filename_cache:
            document = document_repo.get_by_id(document_id)
            filename_cache[document_id] = document.filename if document else None
        return filename_cache[document_id]

    return [
        EvidenceItemResponse(
            chunk_id=item.chunk_id,
            document_id=item.document_id,
            filename=filename_for(item.document_id),
            page=item.page,
            section=item.section,
            rank=item.rank,
            retrieval_source=item.retrieval_source.value,
            content_preview=preview(item.content),
            chunk_type=item.metadata.get("chunk_type"),
            audio_start=item.metadata.get("audio_start"),
            audio_end=item.metadata.get("audio_end"),
        )
        for item in evidence
    ]


def _citation_responses(
    citations: list[Citation], document_repo: DocumentRepository
) -> list[CitationResponse]:
    filename_cache: dict[str, str | None] = {}

    def filename_for(document_id: str | None) -> str | None:
        if document_id is None:
            return None
        if document_id not in filename_cache:
            document = document_repo.get_by_id(document_id)
            filename_cache[document_id] = document.filename if document else None
        return filename_cache[document_id]

    return [
        CitationResponse(
            chunk_id=c.chunk_id,
            valid=c.valid,
            status=c.status.value,
            document_id=c.document_id,
            filename=filename_for(c.document_id),
            page=c.page,
            section=c.section,
            chunk_type=c.chunk_type,
            audio_start=c.audio_start,
            audio_end=c.audio_end,
        )
        for c in citations
    ]


def _contradiction_response(result: ContradictionResult) -> ContradictionResponse:
    return ContradictionResponse(
        has_conflict=result.has_conflict,
        conflicts=[
            ConflictResponse(
                chunk_id_a=c.chunk_id_a, chunk_id_b=c.chunk_id_b, description=c.description
            )
            for c in result.conflicts
        ],
    )


def _sufficiency_response(result: SufficiencyResult) -> SufficiencyResponse:
    return SufficiencyResponse(sufficient=result.sufficient, reason=result.reason)


def _trace_response(result: StudyResponse) -> StudyTraceResponse:
    trace = result.trace
    return StudyTraceResponse(
        provider=trace.provider,
        model=trace.model,
        stats=StudyStatsResponse(
            requested_count=trace.stats.requested_count,
            generated_count=trace.stats.generated_count,
            validated_count=trace.stats.validated_count,
            rejected_count=trace.stats.rejected_count,
            duplicate_count=trace.stats.duplicate_count,
        ),
        timing=StudyTimingResponse(
            retrieval_ms=trace.timings.retrieval_ms,
            sufficiency_ms=trace.timings.sufficiency_ms,
            generation_ms=trace.timings.generation_ms,
            parsing_ms=trace.timings.parsing_ms,
            validation_ms=trace.timings.validation_ms,
            total_ms=trace.timings.total_ms,
        ),
    )


def _persist(
    conn: sqlite3.Connection,
    result: StudyResponse,
    document_id: str | None,
) -> None:
    if not result.answerable or not result.items:
        return
    StudyItemRepository(conn).save_items(
        request_id=result.request_id,
        mode=result.mode,
        query=result.query,
        document_id=document_id,
        items=result.items,
    )


# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------


@router.post("/summary", response_model=SummaryResponse)
def summary(
    request: SummaryRequest,
    retrieval_service: RetrievalService = Depends(get_retrieval_service),
    study_service: StudyEngineService = Depends(get_study_engine_service),
    conn: sqlite3.Connection = Depends(_get_connection),
) -> SummaryResponse:
    evidence, request_id, retrieval_ms = _retrieve(
        retrieval_service, request.query, request.retrieval_mode, request.top_k, request.document_id
    )
    try:
        length = SummaryLength(request.length)
    except ValueError as exc:
        raise HTTPException(
            status_code=400, detail=f"Invalid summary length: {request.length!r}"
        ) from exc

    try:
        result = study_service.summarize(
            request.query, evidence, length=length, request_id=request_id, retrieval_ms=retrieval_ms
        )
    except StudyError as exc:
        raise _handle_study_error(exc) from exc

    _persist(conn, result, request.document_id)
    document_repo = DocumentRepository(conn)
    item = result.items[0] if result.items else None
    assert item is None or isinstance(item, SummaryItem)
    return SummaryResponse(
        request_id=result.request_id,
        mode=result.mode.value,
        query=result.query,
        answerable=result.answerable,
        reason=result.reason,
        item=(
            SummaryItemResponse(
                content=item.content,
                citations=_citation_responses(item.citations, document_repo),
                source_chunk_ids=item.source_chunk_ids,
            )
            if item is not None
            else None
        ),
        evidence=_build_evidence_items(result.evidence, document_repo),
        sufficiency=_sufficiency_response(result.sufficiency),
        contradictions=_contradiction_response(result.contradictions),
        trace=_trace_response(result),
    )


# ---------------------------------------------------------------------------
# Explain
# ---------------------------------------------------------------------------


@router.post("/explain", response_model=ExplainResponse)
def explain(
    request: ExplainRequest,
    retrieval_service: RetrievalService = Depends(get_retrieval_service),
    study_service: StudyEngineService = Depends(get_study_engine_service),
    conn: sqlite3.Connection = Depends(_get_connection),
) -> ExplainResponse:
    evidence, request_id, retrieval_ms = _retrieve(
        retrieval_service, request.query, request.retrieval_mode, request.top_k, request.document_id
    )
    try:
        style = ExplanationStyle(request.style)
    except ValueError as exc:
        raise HTTPException(
            status_code=400, detail=f"Invalid explanation style: {request.style!r}"
        ) from exc

    try:
        result = study_service.explain(
            request.query, evidence, style=style, request_id=request_id, retrieval_ms=retrieval_ms
        )
    except StudyError as exc:
        raise _handle_study_error(exc) from exc

    _persist(conn, result, request.document_id)
    document_repo = DocumentRepository(conn)
    item = result.items[0] if result.items else None
    assert item is None or isinstance(item, ExplanationItem)
    return ExplainResponse(
        request_id=result.request_id,
        mode=result.mode.value,
        query=result.query,
        answerable=result.answerable,
        reason=result.reason,
        item=(
            SummaryItemResponse(
                content=item.content,
                citations=_citation_responses(item.citations, document_repo),
                source_chunk_ids=item.source_chunk_ids,
            )
            if item is not None
            else None
        ),
        evidence=_build_evidence_items(result.evidence, document_repo),
        sufficiency=_sufficiency_response(result.sufficiency),
        contradictions=_contradiction_response(result.contradictions),
        trace=_trace_response(result),
    )


# ---------------------------------------------------------------------------
# Compare
# ---------------------------------------------------------------------------


@router.post("/compare", response_model=CompareResponse)
def compare(
    request: CompareRequest,
    retrieval_service: RetrievalService = Depends(get_retrieval_service),
    study_service: StudyEngineService = Depends(get_study_engine_service),
    conn: sqlite3.Connection = Depends(_get_connection),
) -> CompareResponse:
    evidence_a, request_id, retrieval_ms_a = _retrieve(
        retrieval_service,
        request.topic_a,
        request.retrieval_mode,
        request.top_k,
        request.document_id,
    )
    evidence_b, _, retrieval_ms_b = _retrieve(
        retrieval_service,
        request.topic_b,
        request.retrieval_mode,
        request.top_k,
        request.document_id,
    )
    retrieval_ms = (retrieval_ms_a or 0.0) + (retrieval_ms_b or 0.0)

    try:
        result = study_service.compare(
            request.topic_a,
            request.topic_b,
            evidence_a,
            evidence_b,
            request_id=request_id,
            retrieval_ms=retrieval_ms,
        )
    except StudyError as exc:
        raise _handle_study_error(exc) from exc

    _persist(conn, result, request.document_id)
    document_repo = DocumentRepository(conn)
    item = result.items[0] if result.items else None
    assert item is None or isinstance(item, ComparisonItem)
    return CompareResponse(
        request_id=result.request_id,
        mode=result.mode.value,
        query=result.query,
        answerable=result.answerable,
        reason=result.reason,
        item=(
            ComparisonItemResponse(
                topic_a=item.topic_a,
                topic_b=item.topic_b,
                incomplete_for=item.incomplete_for,
                aspects=[
                    ComparisonAspectResponse(
                        aspect=a.aspect,
                        topic_a=a.topic_a,
                        topic_b=a.topic_b,
                        citations=_citation_responses(a.citations, document_repo),
                        source_chunk_ids=a.source_chunk_ids,
                    )
                    for a in item.aspects
                ],
            )
            if item is not None
            else None
        ),
        evidence=_build_evidence_items(result.evidence, document_repo),
        sufficiency=_sufficiency_response(result.sufficiency),
        contradictions=_contradiction_response(result.contradictions),
        trace=_trace_response(result),
    )


# ---------------------------------------------------------------------------
# Quiz
# ---------------------------------------------------------------------------


@router.post("/quiz", response_model=QuizResponse)
def quiz(
    request: QuizRequest,
    retrieval_service: RetrievalService = Depends(get_retrieval_service),
    study_service: StudyEngineService = Depends(get_study_engine_service),
    conn: sqlite3.Connection = Depends(_get_connection),
) -> QuizResponse:
    evidence, request_id, retrieval_ms = _retrieve(
        retrieval_service, request.query, request.retrieval_mode, request.top_k, request.document_id
    )
    try:
        difficulty = Difficulty(request.difficulty)
        question_type = QuestionType(request.question_type)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    try:
        result = study_service.generate_quiz(
            request.query,
            evidence,
            count=request.count,
            difficulty=difficulty,
            question_type=question_type,
            request_id=request_id,
            retrieval_ms=retrieval_ms,
        )
    except StudyError as exc:
        raise _handle_study_error(exc) from exc

    _persist(conn, result, request.document_id)
    document_repo = DocumentRepository(conn)
    items = [item for item in result.items if isinstance(item, QuizQuestion)]
    return QuizResponse(
        request_id=result.request_id,
        mode=result.mode.value,
        query=result.query,
        answerable=result.answerable,
        reason=result.reason,
        items=[
            QuizQuestionResponse(
                question=q.question,
                expected_answer=q.expected_answer,
                explanation=q.explanation,
                difficulty=q.difficulty.value,
                question_type=q.question_type.value,
                citations=_citation_responses(q.citations, document_repo),
                source_chunk_ids=q.source_chunk_ids,
            )
            for q in items
        ],
        evidence=_build_evidence_items(result.evidence, document_repo),
        sufficiency=_sufficiency_response(result.sufficiency),
        contradictions=_contradiction_response(result.contradictions),
        trace=_trace_response(result),
    )


# ---------------------------------------------------------------------------
# MCQ
# ---------------------------------------------------------------------------


@router.post("/mcq", response_model=MCQResponse)
def mcq(
    request: MCQRequest,
    retrieval_service: RetrievalService = Depends(get_retrieval_service),
    study_service: StudyEngineService = Depends(get_study_engine_service),
    conn: sqlite3.Connection = Depends(_get_connection),
) -> MCQResponse:
    evidence, request_id, retrieval_ms = _retrieve(
        retrieval_service, request.query, request.retrieval_mode, request.top_k, request.document_id
    )
    try:
        difficulty = Difficulty(request.difficulty)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    try:
        result = study_service.generate_mcqs(
            request.query,
            evidence,
            count=request.count,
            difficulty=difficulty,
            request_id=request_id,
            retrieval_ms=retrieval_ms,
        )
    except StudyError as exc:
        raise _handle_study_error(exc) from exc

    _persist(conn, result, request.document_id)
    document_repo = DocumentRepository(conn)
    items = [item for item in result.items if isinstance(item, MCQItem)]
    return MCQResponse(
        request_id=result.request_id,
        mode=result.mode.value,
        query=result.query,
        answerable=result.answerable,
        reason=result.reason,
        items=[
            MCQItemResponse(
                question=m.question,
                options=[MCQOptionResponse(id=o.id, text=o.text) for o in m.options],
                correct_option=m.correct_option,
                explanation=m.explanation,
                difficulty=m.difficulty.value,
                citations=_citation_responses(m.citations, document_repo),
                source_chunk_ids=m.source_chunk_ids,
            )
            for m in items
        ],
        evidence=_build_evidence_items(result.evidence, document_repo),
        sufficiency=_sufficiency_response(result.sufficiency),
        contradictions=_contradiction_response(result.contradictions),
        trace=_trace_response(result),
    )


# ---------------------------------------------------------------------------
# Flashcards
# ---------------------------------------------------------------------------


@router.post("/flashcards", response_model=FlashcardsResponse)
def flashcards(
    request: FlashcardsRequest,
    retrieval_service: RetrievalService = Depends(get_retrieval_service),
    study_service: StudyEngineService = Depends(get_study_engine_service),
    conn: sqlite3.Connection = Depends(_get_connection),
) -> FlashcardsResponse:
    evidence, request_id, retrieval_ms = _retrieve(
        retrieval_service, request.query, request.retrieval_mode, request.top_k, request.document_id
    )
    try:
        difficulty = Difficulty(request.difficulty)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    try:
        result = study_service.generate_flashcards(
            request.query,
            evidence,
            count=request.count,
            difficulty=difficulty,
            request_id=request_id,
            retrieval_ms=retrieval_ms,
        )
    except StudyError as exc:
        raise _handle_study_error(exc) from exc

    _persist(conn, result, request.document_id)
    document_repo = DocumentRepository(conn)
    items = [item for item in result.items if isinstance(item, Flashcard)]
    return FlashcardsResponse(
        request_id=result.request_id,
        mode=result.mode.value,
        query=result.query,
        answerable=result.answerable,
        reason=result.reason,
        items=[
            FlashcardResponse(
                front=f.front,
                back=f.back,
                explanation=f.explanation,
                difficulty=f.difficulty.value,
                citations=_citation_responses(f.citations, document_repo),
                source_chunk_ids=f.source_chunk_ids,
            )
            for f in items
        ],
        evidence=_build_evidence_items(result.evidence, document_repo),
        sufficiency=_sufficiency_response(result.sufficiency),
        contradictions=_contradiction_response(result.contradictions),
        trace=_trace_response(result),
    )
