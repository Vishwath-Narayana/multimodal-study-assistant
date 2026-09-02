# Ablation Study Plan

Status: rows **A–F are now runnable** as of Phase 2 (`RetrievalMode.BM25`
through `full_baseline` in `app/retrieval/service.py`, plus
`app/retrieval/hybrid.py::inspect_union` for C's "no fusion strategy"
variant) — see the Phase 2 dev-benchmark numbers in
[docs/research/evaluation-plan.md](evaluation-plan.md) for a first (small,
dev-scale, HyDE-mocked) pass over A/B/D/F-equivalent modes. Row G and the
full extension ladder remain **plan only**, pending Phase 3+ (grounded
generation, explainability).

## Baseline Reproduction Ladder

| Configuration | Description | Phase 2 equivalent |
|---|---|---|
| A | BM25 only | `RetrievalMode.BM25` |
| B | FAISS only | `RetrievalMode.DENSE` |
| C | BM25 + FAISS (no fusion strategy — simple concat/dedup) | `hybrid.inspect_union()`, explicitly labeled as an inspection mode, not a ranking |
| D | BM25 + FAISS + RRF | `RetrievalMode.HYBRID_RRF` |
| E | D + HyDE | `RetrievalMode.HYBRID_RRF_HYDE` |
| F | E + Cross-Encoder Reranker | `RetrievalMode.FULL_BASELINE` |
| G | Full EduRAG baseline (F + grounded generation + explainability) | not yet implemented (Phase 3+) |

## Extension Ladder (built on G)

| Configuration | Adds |
|---|---|
| H1 | G + parent/child hierarchical retrieval |
| H2 | H1 + evidence sufficiency detection + abstention |
| H3 | H2 + contradiction detection |
| H4 | H3 + visual evidence preservation (image + OCR + VLM, not caption-only) |
| H | All of the above together (full baseline + our improvements) |

## Method

- Each configuration is run against the same fixed evaluation dataset and
  query set for a given ablation pass.
- Metrics per [docs/research/evaluation-plan.md](evaluation-plan.md) are
  recorded per configuration under `evaluation/experiments/`.
- Comparisons are always made against the immediately preceding row (e.g.
  F vs. E isolates the reranker's contribution), not just against the
  final configuration, so each component's marginal effect is visible.
- No row in either ladder is skipped when reporting — a component that
  turns out not to help is reported as such, not omitted.

## Non-Goals

This plan does not currently include hyperparameter sweeps (e.g. RRF k,
chunk size) — those are separate, smaller experiments recorded independently
once the baseline ladder above has real numbers.
