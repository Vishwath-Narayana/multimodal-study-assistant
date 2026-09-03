from __future__ import annotations

import pytest

from app.generation.attribution import DeterministicChunkAttributor
from app.generation.citations import DeterministicCitationValidator
from app.generation.claims import DeterministicClaimSplitter
from app.generation.contradiction import LexicalContradictionChecker
from app.generation.errors import EmptyQueryError, ProviderUnavailableError
from app.generation.service import GenerationService, GenerationServiceConfig
from app.generation.sufficiency import HeuristicSufficiencyChecker, SufficiencyConfig
from app.generation.token_grounding import DeterministicTokenGrounder
from tests.generation.conftest import make_result
from tests.generation.fakes import FakeGenerator

EVIDENCE = [
    make_result(
        "c1",
        "Photosynthesis converts light energy into chemical energy.",
        rerank_score=2.0,
    )
]


def _service(generator: FakeGenerator, **config_overrides: bool) -> GenerationService:
    sufficiency = HeuristicSufficiencyChecker(
        SufficiencyConfig(min_chunks=1, min_lexical_overlap=0.05, min_reranker_score=0.0)
    )
    token_grounder = DeterministicTokenGrounder()
    config = GenerationServiceConfig(max_tokens=128, temperature=0.0, **config_overrides)
    return GenerationService(
        generator=generator,
        sufficiency_checker=sufficiency,
        citation_validator=DeterministicCitationValidator(),
        attributor=DeterministicChunkAttributor(),
        token_grounder=token_grounder,
        claim_splitter=DeterministicClaimSplitter(token_grounder),
        contradiction_checker=LexicalContradictionChecker(),
        config=config,
    )


def test_sufficient_evidence_produces_grounded_answer() -> None:
    generator = FakeGenerator(
        text="Photosynthesis converts light energy into chemical energy. [chunk:c1]",
        raw_chunk_ids=["c1"],
    )
    service = _service(generator)
    response = service.answer("What is photosynthesis?", EVIDENCE)
    assert response.answerable is True
    assert response.citations[0].valid is True
    assert response.attribution
    assert response.grounding is not None
    assert response.trace.timings.generation_ms is not None


def test_insufficient_evidence_returns_abstention() -> None:
    generator = FakeGenerator()
    service = _service(generator)
    response = service.answer("What is photosynthesis?", [])
    assert response.answerable is False
    assert response.citations == []
    assert "couldn't find enough information" in response.answer
    assert response.trace.timings.generation_ms is None  # generation never ran


def test_provider_failure_propagates() -> None:
    generator = FakeGenerator(unavailable=True)
    service = _service(generator)
    with pytest.raises(ProviderUnavailableError):
        service.answer("What is photosynthesis?", EVIDENCE)


def test_empty_query_raises() -> None:
    generator = FakeGenerator()
    service = _service(generator)
    with pytest.raises(EmptyQueryError):
        service.answer("   ", EVIDENCE)


def test_ablation_disable_all_explainability_stages() -> None:
    generator = FakeGenerator(text="An answer. [chunk:c1]", raw_chunk_ids=["c1"])
    service = _service(
        generator,
        enable_citation_validation=False,
        enable_attribution=False,
        enable_token_grounding=False,
        enable_claim_grounding=False,
        enable_contradiction_check=False,
    )
    response = service.answer("What is photosynthesis?", EVIDENCE)
    assert response.answerable is True
    assert response.citations == []
    assert response.attribution == []
    assert response.grounding is None
    assert response.claim_groundings == []
    assert response.contradictions.has_conflict is False


def test_ablation_disable_sufficiency_check_forces_generation() -> None:
    generator = FakeGenerator(text="An answer despite no evidence.", raw_chunk_ids=[])
    service = _service(generator, enable_sufficiency_check=False)
    response = service.answer("What is photosynthesis?", [])
    assert response.answerable is True
    assert response.answer == "An answer despite no evidence."


def test_deterministic_response_for_same_inputs() -> None:
    generator = FakeGenerator(
        text="Photosynthesis converts light energy. [chunk:c1]", raw_chunk_ids=["c1"]
    )
    service = _service(generator)
    first = service.answer("What is photosynthesis?", EVIDENCE)
    second = service.answer("What is photosynthesis?", EVIDENCE)
    assert first.answer == second.answer
    assert [c.attribution_score for c in first.attribution] == [
        c.attribution_score for c in second.attribution
    ]
