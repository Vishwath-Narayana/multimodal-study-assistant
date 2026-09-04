from __future__ import annotations

from app.generation.citations import DeterministicCitationValidator
from app.generation.contradiction import ContradictionConfig, LexicalContradictionChecker
from app.generation.sufficiency import HeuristicSufficiencyChecker, SufficiencyConfig
from app.retrieval.models import RetrievalResult, RetrievalSource
from app.study.service import StudyEngineService, StudyEngineServiceConfig
from tests.study.fakes import FakeStudyGenerator


def make_result(
    chunk_id: str,
    content: str,
    document_id: str = "doc-1",
    rank: int = 1,
    score: float = 1.0,
    retrieval_source: RetrievalSource = RetrievalSource.RERANKER,
    rerank_score: float | None = 1.0,
) -> RetrievalResult:
    return RetrievalResult(
        chunk_id=chunk_id,
        document_id=document_id,
        content=content,
        score=score,
        rank=rank,
        retrieval_source=retrieval_source,
        rerank_score=rerank_score,
    )


def make_service(
    generator: FakeStudyGenerator | None = None,
    known_chunk_ids: set[str] | None = None,
    min_chunks: int = 1,
    min_lexical_overlap: float = 0.0,
    min_reranker_score: float = -1.0,
    enable_sufficiency_check: bool = True,
    enable_citation_validation: bool = True,
    enable_contradiction_check: bool = True,
) -> StudyEngineService:
    return StudyEngineService(
        generator=generator or FakeStudyGenerator(),
        sufficiency_checker=HeuristicSufficiencyChecker(
            SufficiencyConfig(
                min_chunks=min_chunks,
                min_lexical_overlap=min_lexical_overlap,
                min_reranker_score=min_reranker_score,
            )
        ),
        citation_validator=DeterministicCitationValidator(known_chunk_ids=known_chunk_ids),
        contradiction_checker=LexicalContradictionChecker(ContradictionConfig()),
        config=StudyEngineServiceConfig(
            max_tokens=512,
            temperature=0.2,
            min_count=1,
            max_count=20,
            enable_sufficiency_check=enable_sufficiency_check,
            enable_citation_validation=enable_citation_validation,
            enable_contradiction_check=enable_contradiction_check,
        ),
    )
