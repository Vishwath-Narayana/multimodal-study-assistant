# Ablation Study Plan

Status: **plan only**, no runs performed yet. This defines the pipeline
configurations we will compare once retrieval and generation exist, to
isolate the contribution of each component and each proposed extension.

## Baseline Reproduction Ladder

| Configuration | Description |
|---|---|
| A | BM25 only |
| B | FAISS only |
| C | BM25 + FAISS (no fusion strategy — simple concat/dedup) |
| D | BM25 + FAISS + RRF |
| E | D + HyDE |
| F | E + Cross-Encoder Reranker |
| G | Full EduRAG baseline (F + grounded generation + explainability) |

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
