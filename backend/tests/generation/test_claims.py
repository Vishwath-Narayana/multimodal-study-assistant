from __future__ import annotations

from app.generation.claims import DeterministicClaimSplitter
from app.generation.models import Citation, CitationStatus
from tests.generation.conftest import make_result

EVIDENCE = [
    make_result(
        "c1", "Photosynthesis converts light energy into chemical energy.", document_id="doc-1"
    ),
    make_result(
        "c2", "Cellular respiration releases energy stored in glucose.", document_id="doc-1"
    ),
]


def test_splits_into_multiple_claims() -> None:
    splitter = DeterministicClaimSplitter()
    answer = (
        "Photosynthesis converts light energy into chemical energy. [chunk:c1] "
        "Cellular respiration releases energy stored in glucose. [chunk:c2]"
    )
    citations = [
        Citation(chunk_id="c1", status=CitationStatus.VALID),
        Citation(chunk_id="c2", status=CitationStatus.VALID),
    ]
    claims = splitter.split_and_attribute(answer, EVIDENCE, citations)
    assert len(claims) == 2
    assert claims[0].supporting_chunk_ids == ["c1"]
    assert claims[1].supporting_chunk_ids == ["c2"]


def test_claim_without_citation_still_gets_lexical_support() -> None:
    splitter = DeterministicClaimSplitter()
    answer = "Photosynthesis converts light energy into chemical energy."
    claims = splitter.split_and_attribute(answer, EVIDENCE, [])
    assert claims
    assert "c1" in claims[0].supporting_chunk_ids


def test_invalid_citation_is_not_counted_as_supporting() -> None:
    splitter = DeterministicClaimSplitter()
    answer = "Some claim with a bogus citation. [chunk:fabricated]"
    citations = [Citation(chunk_id="fabricated", status=CitationStatus.UNKNOWN_CHUNK)]
    claims = splitter.split_and_attribute(answer, EVIDENCE, citations)
    assert "fabricated" not in claims[0].supporting_chunk_ids


def test_empty_answer_yields_no_claims() -> None:
    splitter = DeterministicClaimSplitter()
    assert splitter.split_and_attribute("", EVIDENCE, []) == []


def test_each_claim_carries_a_grounding_ratio() -> None:
    splitter = DeterministicClaimSplitter()
    claims = splitter.split_and_attribute(
        "Photosynthesis converts light energy into chemical energy.", EVIDENCE, []
    )
    assert claims[0].grounding_ratio is not None
