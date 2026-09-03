from __future__ import annotations

from app.generation.citations import (
    DeterministicCitationValidator,
    extract_citations,
    strip_citation_markers,
)
from app.generation.models import CitationStatus
from tests.generation.conftest import make_result

EVIDENCE = [
    make_result(
        "doc-1::chunk::00001", "Photosynthesis converts light energy.", document_id="doc-1"
    ),
    make_result("doc-1::chunk::00002", "Chlorophyll absorbs light.", document_id="doc-1"),
]


def test_extract_citations_finds_all_and_dedupes_preserving_order() -> None:
    text = "Claim one [chunk:doc-1::chunk::00001]. Claim two [chunk:doc-1::chunk::00002]. " \
        "Repeat [chunk:doc-1::chunk::00001]."
    assert extract_citations(text) == ["doc-1::chunk::00001", "doc-1::chunk::00002"]


def test_extract_citations_returns_empty_for_no_markers() -> None:
    assert extract_citations("An answer with no citation syntax at all.") == []


def test_extract_citations_ignores_malformed_markers() -> None:
    assert extract_citations("See [chunk: not-closed") == []


def test_strip_citation_markers_removes_markers_only() -> None:
    text = "Claim [chunk:doc-1::chunk::00001] continues here."
    assert strip_citation_markers(text) == "Claim  continues here."


def test_validator_accepts_chunk_present_in_evidence() -> None:
    validator = DeterministicCitationValidator()
    citations = validator.validate(["doc-1::chunk::00001"], EVIDENCE)
    assert len(citations) == 1
    assert citations[0].valid is True
    assert citations[0].status == CitationStatus.VALID
    assert citations[0].document_id == "doc-1"


def test_validator_rejects_nonexistent_chunk_as_unknown() -> None:
    validator = DeterministicCitationValidator()
    citations = validator.validate(["totally-fabricated-id"], EVIDENCE)
    assert citations[0].valid is False
    assert citations[0].status == CitationStatus.UNKNOWN_CHUNK
    assert citations[0].document_id is None


def test_validator_distinguishes_real_but_non_retrieved_chunk() -> None:
    validator = DeterministicCitationValidator(
        known_chunk_ids={"doc-1::chunk::00001", "doc-1::chunk::00002", "doc-2::chunk::00001"}
    )
    citations = validator.validate(["doc-2::chunk::00001"], EVIDENCE)
    assert citations[0].valid is False
    assert citations[0].status == CitationStatus.NOT_IN_RETRIEVED_EVIDENCE


def test_validator_rejects_metadata_mismatch_is_not_possible_by_construction() -> None:
    """Citation metadata always comes from the evidence item itself, so a
    valid citation can never carry mismatched metadata (spec: 'citation
    metadata matches the underlying chunk') — this is a design invariant,
    exercised here by confirming the returned page/section always equal
    the retrieved chunk's own page/section."""
    evidence = [make_result("c1", "content", page=7, section="Intro")]
    validator = DeterministicCitationValidator()
    citations = validator.validate(["c1"], evidence)
    assert citations[0].page == 7
    assert citations[0].section == "Intro"
