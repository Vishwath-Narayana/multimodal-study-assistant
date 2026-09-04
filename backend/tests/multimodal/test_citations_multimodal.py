"""Citation validation carries modality identification (spec section 21)."""

from __future__ import annotations

from app.generation.citations import DeterministicCitationValidator
from app.retrieval.models import RetrievalResult, RetrievalSource


def _evidence_item(chunk_id: str, metadata: dict) -> RetrievalResult:
    return RetrievalResult(
        chunk_id=chunk_id,
        document_id="doc1",
        content="content",
        score=1.0,
        rank=1,
        retrieval_source=RetrievalSource.RERANKER,
        page=7,
        metadata=metadata,
    )


def test_valid_image_citation_carries_chunk_type() -> None:
    evidence = [_evidence_item("c1", {"chunk_type": "image", "original_artifact": "p.png"})]
    citations = DeterministicCitationValidator().validate(["c1"], evidence)
    assert citations[0].valid is True
    assert citations[0].chunk_type == "image"


def test_valid_transcript_citation_carries_timestamps() -> None:
    evidence = [
        _evidence_item(
            "c1", {"chunk_type": "transcript", "audio_start": 751.0, "audio_end": 788.0}
        )
    ]
    citations = DeterministicCitationValidator().validate(["c1"], evidence)
    assert citations[0].chunk_type == "transcript"
    assert citations[0].audio_start == 751.0
    assert citations[0].audio_end == 788.0


def test_invalid_citation_has_no_chunk_type() -> None:
    citations = DeterministicCitationValidator().validate(["unknown_chunk"], [])
    assert citations[0].valid is False
    assert citations[0].chunk_type is None
