"""Grounded-generation query endpoint (Phase 3).

`POST /chat/query`: retrieves evidence via the existing Phase 2
`RetrievalService` (no retrieval logic is reimplemented here), then runs it
through `GenerationService` (evidence sufficiency -> grounded generation ->
citation validation -> attribution -> token grounding -> claim grounding ->
contradiction checking) and returns one structured response. Not a chat/
session API — no conversation memory, single query in, single structured
answer out (see docs/roadmap.md Phase 3 scope).
"""

from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends, HTTPException

from app.api.retrieval import _ERROR_STATUS as _RETRIEVAL_ERROR_STATUS
from app.api.retrieval import _get_connection, get_retrieval_service
from app.core.config import Settings, get_settings
from app.generation.attribution import DeterministicChunkAttributor
from app.generation.citations import DeterministicCitationValidator
from app.generation.claims import DeterministicClaimSplitter
from app.generation.contradiction import ContradictionConfig, LexicalContradictionChecker
from app.generation.errors import (
    EmptyQueryError,
    GenerationError,
    GenerationFailedError,
    ProviderUnavailableError,
)
from app.generation.generator import OllamaGenerator
from app.generation.interfaces import Generator
from app.generation.models import GenerationResponse
from app.generation.service import GenerationService, GenerationServiceConfig
from app.generation.sufficiency import HeuristicSufficiencyChecker, SufficiencyConfig
from app.generation.token_grounding import DeterministicTokenGrounder
from app.ingestion.repository import ChunkRepository, DocumentRepository
from app.retrieval.errors import RetrievalError
from app.retrieval.llm_client import OllamaClient
from app.retrieval.service import RetrievalService
from app.schemas.generation import (
    ChatQueryRequest,
    ChatQueryResponse,
    CitationResponse,
    ClaimGroundingResponse,
    ConflictResponse,
    ContradictionResponse,
    EvidenceItemResponse,
    GenerationTimingResponse,
    GroundingResponse,
    SufficiencyResponse,
    preview,
)

router = APIRouter(prefix="/chat", tags=["chat"])

# Same lifecycle discipline as app.api.retrieval: heavy/long-lived clients
# are cached per process, keyed by their configuration, with a test-only
# reset hook.
_generator_cache: dict[tuple[str, str], Generator] = {}


def reset_generator_cache() -> None:
    """Test-only hook, mirroring `app.api.retrieval.reset_model_caches`."""
    _generator_cache.clear()


def get_generator(settings: Settings = Depends(get_settings)) -> Generator:
    key = (settings.llm_provider, settings.llm_model)
    generator = _generator_cache.get(key)
    if generator is None:
        if settings.llm_provider != "ollama":
            raise HTTPException(
                status_code=500,
                detail=f"Unsupported llm_provider '{settings.llm_provider}'.",
            )
        client = OllamaClient(
            settings.ollama_base_url, settings.llm_model, settings.generation_timeout_seconds
        )
        generator = OllamaGenerator(client)
        _generator_cache[key] = generator
    return generator


def get_generation_service(
    settings: Settings = Depends(get_settings),
    conn: sqlite3.Connection = Depends(_get_connection),
    generator: Generator = Depends(get_generator),
) -> GenerationService:
    known_chunk_ids = {c.id for c in ChunkRepository(conn).list_all()}

    sufficiency_checker = HeuristicSufficiencyChecker(
        SufficiencyConfig(
            min_chunks=settings.sufficiency_min_chunks,
            min_lexical_overlap=settings.sufficiency_min_lexical_overlap,
            min_reranker_score=settings.sufficiency_min_reranker_score,
        )
    )
    citation_validator = DeterministicCitationValidator(known_chunk_ids=known_chunk_ids)
    attributor = DeterministicChunkAttributor()
    token_grounder = DeterministicTokenGrounder(grounded_threshold=settings.grounding_threshold)
    claim_splitter = DeterministicClaimSplitter(token_grounder)
    contradiction_checker = LexicalContradictionChecker(
        ContradictionConfig(
            topic_overlap_threshold=settings.contradiction_topic_overlap_threshold
        )
    )
    config = GenerationServiceConfig(
        max_tokens=settings.generation_max_tokens,
        temperature=settings.generation_temperature,
    )
    return GenerationService(
        generator=generator,
        sufficiency_checker=sufficiency_checker,
        citation_validator=citation_validator,
        attributor=attributor,
        token_grounder=token_grounder,
        claim_splitter=claim_splitter,
        contradiction_checker=contradiction_checker,
        config=config,
    )


_ERROR_STATUS: dict[type[GenerationError], int] = {
    EmptyQueryError: 400,
    ProviderUnavailableError: 503,
    GenerationFailedError: 502,
}


def _build_response(
    result: GenerationResponse, conn: sqlite3.Connection
) -> ChatQueryResponse:
    document_repo = DocumentRepository(conn)
    filename_cache: dict[str, str | None] = {}

    def filename_for(document_id: str) -> str | None:
        if document_id not in filename_cache:
            document = document_repo.get_by_id(document_id)
            filename_cache[document_id] = document.filename if document else None
        return filename_cache[document_id]

    attribution_by_chunk = {a.chunk_id: a for a in result.attribution}

    evidence_items = [
        EvidenceItemResponse(
            chunk_id=item.chunk_id,
            document_id=item.document_id,
            filename=filename_for(item.document_id),
            page=item.page,
            section=item.section,
            rank=item.rank,
            retrieval_source=item.retrieval_source.value,
            rerank_score=item.rerank_score,
            content_preview=preview(item.content),
            attribution_score=(
                attribution_by_chunk[item.chunk_id].attribution_score
                if item.chunk_id in attribution_by_chunk
                else None
            ),
            attribution_rank=(
                attribution_by_chunk[item.chunk_id].rank
                if item.chunk_id in attribution_by_chunk
                else None
            ),
            chunk_type=item.metadata.get("chunk_type"),
            audio_start=item.metadata.get("audio_start"),
            audio_end=item.metadata.get("audio_end"),
            ocr_text=item.metadata.get("ocr_text"),
            vlm_description=item.metadata.get("vlm_description"),
            original_artifact=item.metadata.get("original_artifact"),
            table_content=item.metadata.get("table_content"),
        )
        for item in result.evidence
    ]

    citation_items = [
        CitationResponse(
            chunk_id=c.chunk_id,
            valid=c.valid,
            status=c.status.value,
            document_id=c.document_id,
            filename=filename_for(c.document_id) if c.document_id else None,
            page=c.page,
            section=c.section,
            chunk_type=c.chunk_type,
            audio_start=c.audio_start,
            audio_end=c.audio_end,
        )
        for c in result.citations
    ]

    grounding_response = (
        GroundingResponse(
            grounding_ratio=result.grounding.grounding_ratio,
            grounded_token_count=result.grounding.grounded_token_count,
            total_token_count=result.grounding.total_token_count,
        )
        if result.grounding is not None
        else None
    )

    claim_items = [
        ClaimGroundingResponse(
            claim=c.claim,
            supporting_chunk_ids=c.supporting_chunk_ids,
            grounding_ratio=c.grounding_ratio,
        )
        for c in result.claim_groundings
    ]

    contradiction_response = ContradictionResponse(
        has_conflict=result.contradictions.has_conflict,
        conflicts=[
            ConflictResponse(
                chunk_id_a=c.chunk_id_a, chunk_id_b=c.chunk_id_b, description=c.description
            )
            for c in result.contradictions.conflicts
        ],
    )

    timings = result.trace.timings
    timing_response = GenerationTimingResponse(
        retrieval_ms=timings.retrieval_ms,
        sufficiency_ms=timings.sufficiency_ms,
        generation_ms=timings.generation_ms,
        citation_validation_ms=timings.citation_validation_ms,
        attribution_ms=timings.attribution_ms,
        grounding_ms=timings.grounding_ms,
        contradiction_ms=timings.contradiction_ms,
        total_ms=timings.total_ms,
    )

    return ChatQueryResponse(
        request_id=result.request_id,
        query=result.query,
        answer=result.answer,
        answerable=result.answerable,
        sufficiency=SufficiencyResponse(
            sufficient=result.sufficiency.sufficient, reason=result.sufficiency.reason
        ),
        evidence=evidence_items,
        citations=citation_items,
        grounding=grounding_response,
        claim_groundings=claim_items,
        contradictions=contradiction_response,
        timing=timing_response,
    )


@router.post("/query", response_model=ChatQueryResponse)
def query(
    request: ChatQueryRequest,
    retrieval_service: RetrievalService = Depends(get_retrieval_service),
    generation_service: GenerationService = Depends(get_generation_service),
    conn: sqlite3.Connection = Depends(_get_connection),
) -> ChatQueryResponse:
    try:
        evidence, retrieval_trace = retrieval_service.retrieve(
            request.query, request.retrieval_mode, top_k=request.top_k
        )
    except RetrievalError as exc:
        status_code = next(
            (
                code
                for error_type, code in _RETRIEVAL_ERROR_STATUS.items()
                if isinstance(exc, error_type)
            ),
            500,
        )
        raise HTTPException(status_code=status_code, detail=exc.message) from exc

    try:
        result = generation_service.answer(
            request.query,
            evidence,
            request_id=retrieval_trace.request_id,
            retrieval_ms=retrieval_trace.timings.total_ms,
        )
    except GenerationError as exc:
        status_code = next(
            (code for error_type, code in _ERROR_STATUS.items() if isinstance(exc, error_type)),
            500,
        )
        raise HTTPException(status_code=status_code, detail=exc.message) from exc

    return _build_response(result, conn)
