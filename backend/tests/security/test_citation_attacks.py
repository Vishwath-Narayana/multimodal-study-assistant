"""Phase 8N: citation-attack security tests (spec section 8F/8F.1).

`DeterministicCitationValidator` is the single place that decides whether a
model-emitted `[chunk:<id>]` citation is trustworthy. These tests attack it
directly: a fabricated id, an id belonging to a real chunk from a different
request's retrieved set, a stale id from a prior request, and an id that
exists in the corpus but was never retrieved for *this* query (spec section
8F.1: "prevent ... cross-request citation leakage").
"""

from __future__ import annotations

from app.generation.citations import DeterministicCitationValidator, extract_citations
from app.generation.models import CitationStatus
from tests.generation.conftest import make_result


def test_fake_chunk_id_is_rejected() -> None:
    evidence = [make_result("real-chunk-1", "Real content.")]
    validator = DeterministicCitationValidator()
    citations = validator.validate(["fake-chunk-id-planted-by-model"], evidence)
    assert citations[0].status == CitationStatus.UNKNOWN_CHUNK
    assert citations[0].valid is False


def test_nonexistent_chunk_id_with_known_corpus_is_still_unknown() -> None:
    evidence = [make_result("real-chunk-1", "Real content.")]
    validator = DeterministicCitationValidator(known_chunk_ids={"real-chunk-1"})
    citations = validator.validate(["totally-made-up-id"], evidence)
    assert citations[0].status == CitationStatus.UNKNOWN_CHUNK


def test_citation_to_a_chunk_from_a_different_document_not_in_this_request_is_rejected() -> None:
    """A chunk that genuinely exists in the corpus (e.g. from another
    document the model was never given as evidence for this query) must
    still be rejected as NOT_IN_RETRIEVED_EVIDENCE — the corpus containing
    it is not enough; it must have been part of *this* request's retrieval
    (spec section 8F.1: evidence boundary)."""
    evidence = [make_result("doc-a::chunk::0", "Evidence actually retrieved.", document_id="doc-a")]
    validator = DeterministicCitationValidator(
        known_chunk_ids={"doc-a::chunk::0", "doc-b::chunk::5"}
    )
    citations = validator.validate(["doc-b::chunk::5"], evidence)
    assert citations[0].status == CitationStatus.NOT_IN_RETRIEVED_EVIDENCE
    assert citations[0].valid is False


def test_stale_citation_from_a_prior_requests_evidence_is_rejected() -> None:
    """Simulates a model "remembering" a chunk id it saw cited in an
    earlier, unrelated request/response and reusing it — validation is
    always scoped to the evidence passed in for *this* call, never to any
    global or cross-request state."""
    previous_request_evidence = [make_result("doc-x::chunk::1", "Old content.")]
    validator = DeterministicCitationValidator()
    # First request: this citation is legitimately valid.
    first = validator.validate(["doc-x::chunk::1"], previous_request_evidence)
    assert first[0].valid is True

    # A new request retrieves entirely different evidence; the same
    # chunk_id string, now stale, must not validate against it.
    new_request_evidence = [make_result("doc-y::chunk::2", "New content.")]
    second = validator.validate(["doc-x::chunk::1"], new_request_evidence)
    assert second[0].status == CitationStatus.UNKNOWN_CHUNK
    assert second[0].valid is False


def test_citation_not_present_in_retrieved_context_at_all() -> None:
    evidence: list = []
    validator = DeterministicCitationValidator()
    citations = validator.validate(["anything"], evidence)
    assert citations[0].valid is False


def test_valid_citation_still_passes() -> None:
    """Regression guard: the attack tests above must not have made the
    validator reject legitimate citations too."""
    evidence = [make_result("doc-a::chunk::0", "Real content.", document_id="doc-a", page=3)]
    validator = DeterministicCitationValidator()
    citations = validator.validate(["doc-a::chunk::0"], evidence)
    assert citations[0].status == CitationStatus.VALID
    assert citations[0].valid is True
    assert citations[0].document_id == "doc-a"
    assert citations[0].page == 3


def test_model_cannot_smuggle_a_citation_shaped_string_that_isnt_the_marker_format() -> None:
    """Extraction only recognizes the literal `[chunk:<id>]` format — any
    other shape a model might use to try to reference something produces
    no extracted citation at all (fail safe, never a best-effort guess)."""
    raw_ids = extract_citations("See citation(chunk_id=admin-doc) for details.")
    assert raw_ids == []


def test_duplicate_citations_to_the_same_valid_chunk_are_deduplicated_on_extraction() -> None:
    raw_ids = extract_citations("[chunk:c1] and again [chunk:c1] and [chunk:c2]")
    assert raw_ids == ["c1", "c2"]
