"""Claim-level grounding: split an answer into claims/sentences and
associate each with the chunks that support it (spec section 13).

**Sentence splitting** (`_split_sentences`): a plain regex split on
`.`/`!`/`?` followed by whitespace. This is a documented, known-imperfect
heuristic — it will mis-split on abbreviations ("e.g.", "Dr.") and decimal
numbers ("3.14"). A full sentence boundary detector was judged out of scope
for Phase 3 (spec: "if the implementation cannot reliably split a complex
sentence, document the limitation rather than pretending it is perfect").

**Attribution per claim**: a claim's supporting chunks are (a) any chunk
explicitly cited with `[chunk:...]` inside that claim, plus (b) any
retrieved chunk whose lexical (Jaccard) overlap with the claim's tokens
exceeds `SUPPORT_OVERLAP_THRESHOLD` — this second rule catches claims the
model forgot to cite, without requiring semantic similarity. Each claim's
`grounding_ratio` reuses `DeterministicTokenGrounder` scoped to just that
claim's text.
"""

from __future__ import annotations

import re

from app.generation.citations import extract_citations, strip_citation_markers
from app.generation.interfaces import ClaimSplitter
from app.generation.models import Citation, ClaimGrounding
from app.generation.token_grounding import DeterministicTokenGrounder
from app.retrieval.models import RetrievalResult
from app.retrieval.tokenizer import tokenize

_SENTENCE_BOUNDARY = re.compile(r"(?<=[.!?])\s+")

SUPPORT_OVERLAP_THRESHOLD = 0.15


def _split_sentences(text: str) -> list[str]:
    stripped = text.strip()
    if not stripped:
        return []
    return [s.strip() for s in _SENTENCE_BOUNDARY.split(stripped) if s.strip()]


def _jaccard(tokens_a: set[str], tokens_b: set[str]) -> float:
    if not tokens_a or not tokens_b:
        return 0.0
    intersection = len(tokens_a & tokens_b)
    union = len(tokens_a | tokens_b)
    return intersection / union if union else 0.0


class DeterministicClaimSplitter(ClaimSplitter):
    def __init__(self, token_grounder: DeterministicTokenGrounder | None = None) -> None:
        self._token_grounder = token_grounder or DeterministicTokenGrounder()

    def split_and_attribute(
        self, answer: str, evidence: list[RetrievalResult], citations: list[Citation]
    ) -> list[ClaimGrounding]:
        valid_chunk_ids = {c.chunk_id for c in citations if c.valid}
        claims: list[ClaimGrounding] = []

        for sentence in _split_sentences(answer):
            cited_here = [cid for cid in extract_citations(sentence) if cid in valid_chunk_ids]
            claim_text = strip_citation_markers(sentence).strip()
            if not claim_text:
                continue

            claim_tokens = set(tokenize(claim_text))
            overlap_supported = [
                item.chunk_id
                for item in evidence
                if item.chunk_id not in cited_here
                and _jaccard(claim_tokens, set(tokenize(item.content)))
                >= SUPPORT_OVERLAP_THRESHOLD
            ]
            supporting = list(dict.fromkeys([*cited_here, *overlap_supported]))

            grounding = self._token_grounder.ground(claim_text, evidence)
            claims.append(
                ClaimGrounding(
                    claim=claim_text,
                    supporting_chunk_ids=supporting,
                    grounding_ratio=grounding.grounding_ratio,
                )
            )

        return claims
