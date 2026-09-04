"""Citation extraction and deterministic validation.

Extraction is a pure string operation over the model's raw output text —
it must match exactly the `[chunk:<chunk_id>]` format specified in
`app.generation.prompts.SYSTEM_INSTRUCTIONS`. A model that free-forms
citations differently produces zero extracted citations rather than a
best-effort guess (spec: "do not silently repair hallucinated citations").
"""

from __future__ import annotations

import re

from app.generation.interfaces import CitationValidator
from app.generation.models import Citation, CitationStatus
from app.retrieval.models import RetrievalResult

# Chunk ids are of the form "{document_id}::chunk::00007" or
# "...::section::00000" (see app.ingestion.chunking) — alphanumeric plus
# "-", "_", ".", ":" covers every id shape currently produced.
_CITATION_PATTERN = re.compile(r"\[chunk:([A-Za-z0-9_\-.:]+)\]")


def extract_citations(answer_text: str) -> list[str]:
    """Return the raw chunk_ids cited in `answer_text`, in first-seen order,
    de-duplicated. Does not check whether any of them are real chunks —
    that is `DeterministicCitationValidator`'s job."""
    seen: dict[str, None] = {}
    for match in _CITATION_PATTERN.finditer(answer_text):
        seen.setdefault(match.group(1), None)
    return list(seen.keys())


def strip_citation_markers(answer_text: str) -> str:
    """The answer text with `[chunk:...]` markers removed, for grounding/
    attribution stages that should score prose, not citation syntax."""
    return _CITATION_PATTERN.sub("", answer_text)


class DeterministicCitationValidator(CitationValidator):
    """Checks each cited chunk_id against the evidence actually retrieved
    for this request, and optionally against the full corpus.

    A citation is VALID only if the chunk_id is present in `evidence` (i.e.
    it was retrieved for *this* query). When `known_chunk_ids` is supplied
    (the full corpus's chunk ids), a citation that names a chunk that
    exists but was never retrieved is reported as
    `NOT_IN_RETRIEVED_EVIDENCE` rather than `UNKNOWN_CHUNK`, so the two
    failure modes ("hallucinated id" vs. "real chunk outside the retrieved
    context") stay distinguishable in the response/trace. Without
    `known_chunk_ids`, both cases collapse to `UNKNOWN_CHUNK` — still
    correctly invalid, just less specific. Either way this is a pure
    lookup: the same inputs always produce the same result.
    """

    def __init__(self, known_chunk_ids: set[str] | None = None) -> None:
        self._known_chunk_ids = known_chunk_ids

    def validate(
        self, raw_chunk_ids: list[str], evidence: list[RetrievalResult]
    ) -> list[Citation]:
        evidence_by_id = {item.chunk_id: item for item in evidence}
        citations: list[Citation] = []
        for chunk_id in raw_chunk_ids:
            item = evidence_by_id.get(chunk_id)
            if item is None:
                exists_outside_evidence = (
                    self._known_chunk_ids is not None and chunk_id in self._known_chunk_ids
                )
                status = (
                    CitationStatus.NOT_IN_RETRIEVED_EVIDENCE
                    if exists_outside_evidence
                    else CitationStatus.UNKNOWN_CHUNK
                )
                citations.append(Citation(chunk_id=chunk_id, status=status))
                continue
            citations.append(
                Citation(
                    chunk_id=chunk_id,
                    status=CitationStatus.VALID,
                    document_id=item.document_id,
                    page=item.page,
                    section=item.section,
                    chunk_type=item.metadata.get("chunk_type"),
                    audio_start=item.metadata.get("audio_start"),
                    audio_end=item.metadata.get("audio_end"),
                )
            )
        return citations
