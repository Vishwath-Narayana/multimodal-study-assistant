"""Phase 7G failure analysis: classifies and preserves question-level
retrieval failures instead of reporting only aggregate scores.

Classification is necessarily coarse and retrieval-only (no generation is
available in this environment — see availability.py): it distinguishes
*why* the correct chunk was missed using signals actually available from
the retrieval trace (which source(s) found it, at what rank), not a full
17-category taxonomy that would require inspecting generation output this
system cannot produce right now. Categories not applicable without
generation (hallucination, citation failure, contradiction-handling
failure, etc.) are omitted rather than guessed.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

from app.benchmarking.metrics_ext import QueryMetrics
from app.benchmarking.wiring import RealStack

FAILURE_THRESHOLD_RECALL_AT_5 = 1.0  # anything below "found everything" is inspected


@dataclass
class FailureCase:
    query_id: str
    category: str
    modality: str
    recall_at_5: float
    reciprocal_rank: float
    retrieved_chunk_ids: list[str]
    relevant_chunk_ids: list[str]
    failure_type: str
    detail: str


def _classify(
    query: str, stack: RealStack, relevant: set[str], retrieved: list[str]
) -> tuple[str, str]:
    """Uses BM25-only and dense-only retrieval (top 20) as diagnostic
    probes to attribute a miss to lexical mismatch, semantic mismatch, or
    a genuine ranking problem after both sources found it.
    """
    bm25_ids = {c.chunk_id for c in stack.bm25.retrieve(query, 20)}
    dense_ids = {c.chunk_id for c in stack.dense.retrieve(query, 20)}

    bm25_found = bool(relevant & bm25_ids)
    dense_found = bool(relevant & dense_ids)

    if not relevant:
        return (
            "no_gold_evidence",
            "Question has no gold chunks (should not reach failure analysis).",
        )
    if not retrieved:
        return "retrieval_miss", "Retriever returned no candidates at all."
    if not bm25_found and not dense_found:
        return (
            "retrieval_miss",
            "Neither BM25 nor dense retrieval found the gold chunk in their top 20 — "
            "likely a genuine corpus/query mismatch, not a fusion/rank problem.",
        )
    if bm25_found and not dense_found:
        return (
            "dense_retrieval_failure",
            "BM25 found the gold chunk but dense (BGE) retrieval did not — likely a "
            "semantic-embedding gap for this query phrasing.",
        )
    if dense_found and not bm25_found:
        return (
            "bm25_lexical_failure",
            "Dense retrieval found the gold chunk but BM25 did not — likely low lexical "
            "overlap between the query and the gold chunk's wording.",
        )
    return (
        "chunk_boundary_or_ranking_problem",
        "Both BM25 and dense retrieval found the gold chunk in their top 20, but it was "
        "ranked outside the final top-k after fusion/reranking.",
    )


def analyze_failures(
    per_query: list[QueryMetrics],
    stack: RealStack,
    query_text_by_id: dict[str, str],
) -> list[FailureCase]:
    cases: list[FailureCase] = []
    for q in per_query:
        if q.recall_at_5 >= FAILURE_THRESHOLD_RECALL_AT_5:
            continue
        relevant = set(q.relevant_chunk_ids)
        query_text = query_text_by_id[q.query_id]
        failure_type, detail = _classify(query_text, stack, relevant, q.retrieved_chunk_ids)
        cases.append(
            FailureCase(
                query_id=q.query_id,
                category=q.category,
                modality=q.modality,
                recall_at_5=q.recall_at_5,
                reciprocal_rank=q.reciprocal_rank,
                retrieved_chunk_ids=q.retrieved_chunk_ids,
                relevant_chunk_ids=q.relevant_chunk_ids,
                failure_type=failure_type,
                detail=detail,
            )
        )
    return cases


def failure_category_counts(cases: list[FailureCase]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for c in cases:
        counts[c.failure_type] = counts.get(c.failure_type, 0) + 1
    return counts


def cases_to_dicts(cases: list[FailureCase]) -> list[dict]:
    return [asdict(c) for c in cases]
