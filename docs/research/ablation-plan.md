# Ablation Study Plan

Status: rows **A–F are runnable** as of Phase 2 (`RetrievalMode.BM25`
through `full_baseline` in `app/retrieval/service.py`, plus
`app/retrieval/hybrid.py::inspect_union` for C's "no fusion strategy"
variant) — see the Phase 2 dev-benchmark numbers in
[docs/research/evaluation-plan.md](evaluation-plan.md) for a first (small,
dev-scale, HyDE-mocked) pass over A/B/D/F-equivalent modes. **Row G is now
runnable as of Phase 3** — `backend/scripts/run_generation_experiment.py`
executes all seven of that row's sub-stages (plain generation through the
full pipeline) via `GenerationServiceConfig`'s ablation toggles — but **has
not yet been run against a real LLM** in this environment (no local Ollama
server was reachable while implementing Phase 3); the script defaults to a
mocked generator and records which one ran. The H1–H4 extension ladder
remains **plan only**, pending Phase 5+ (multimodal retrieval, parent/child
hierarchical retrieval).

## Baseline Reproduction Ladder

| Configuration | Description | Phase 2 equivalent |
|---|---|---|
| A | BM25 only | `RetrievalMode.BM25` |
| B | FAISS only | `RetrievalMode.DENSE` |
| C | BM25 + FAISS (no fusion strategy — simple concat/dedup) | `hybrid.inspect_union()`, explicitly labeled as an inspection mode, not a ranking |
| D | BM25 + FAISS + RRF | `RetrievalMode.HYBRID_RRF` |
| E | D + HyDE | `RetrievalMode.HYBRID_RRF_HYDE` |
| F | E + Cross-Encoder Reranker | `RetrievalMode.FULL_BASELINE` |
| G | Full EduRAG baseline (F + grounded generation + explainability) | `scripts/run_generation_experiment.py` stage `G_full_pipeline` (`RetrievalMode.FULL_BASELINE` + full `GenerationServiceConfig`) |

Row G's sub-stages (A–G reused as generation-pipeline stage names in
`run_generation_experiment.py`, distinct from this table's retrieval-only
A–G) isolate each generation/explainability component's marginal
contribution the same way this table's A–F isolate each retrieval
component's: plain generation → grounded prompt → + evidence sufficiency →
+ citation validation → + attribution → + token/claim grounding → + full
pipeline (contradiction checking included). See
[docs/architecture/generation.md](../architecture/generation.md) "Ablation
Support".

## Extension Ladder (built on G)

Evidence sufficiency/abstention and contradiction detection — originally
planned here as H2/H3 — were **implemented as part of Phase 3 already**
(bundled with generation/explainability per the Phase 3 implementation
brief; see [docs/roadmap.md](../roadmap.md)'s Phase 3 scope note), not as a
separate extension on top of row G. The extension ladder below is updated
accordingly; H1 and H4 (both requiring capabilities Phase 3 explicitly
excludes — hierarchical retrieval, multimodal evidence) remain unimplemented.

| Configuration | Adds | Status |
|---|---|---|
| H1 | G + parent/child hierarchical retrieval | Not started (Phase 7+) |
| ~~H2~~ | ~~H1 + evidence sufficiency detection + abstention~~ | Implemented in Phase 3 (part of row G, not a separate extension) |
| ~~H3~~ | ~~H2 + contradiction detection~~ | Implemented in Phase 3 (part of row G, not a separate extension) |
| H4 | H3 + visual evidence preservation (image + OCR + VLM, not caption-only) | Not started (Phase 5+) |
| H | All of the above together (full baseline + our improvements) | Partially implemented (sufficiency + contradiction, via row G); hierarchical + visual evidence still pending |

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
