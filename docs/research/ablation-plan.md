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
| H4 | H3 + visual evidence preservation (image + OCR + VLM, not caption-only) | **Implemented as of Phase 4** — see [docs/architecture/multimodal.md](../architecture/multimodal.md) |
| H | All of the above together (full baseline + our improvements) | Partially implemented (sufficiency + contradiction, via row G; visual evidence preservation, via H4); hierarchical retrieval still pending |

## Phase 4 Multimodal Ablation Rows

Extends the ladder above with multimodal-specific comparisons (spec
section 30). Rows A-G reuse `RetrievalMode`/`GenerationServiceConfig`
exactly as already implemented — no new toggle infrastructure was needed
for the text-side rows, since multimodal chunks flow through the same
`RetrievalService`/`GenerationService` (see
[docs/architecture/multimodal.md](../architecture/multimodal.md)
"Retrieval Integration").

| Configuration | Adds | Status |
|---|---|---|
| A | Text-only baseline (image/table/transcript chunks excluded from the corpus) | Runnable: pass a chunk set pre-filtered to text types to `BM25Retriever.from_chunks`/`FaissIndexStore.build` |
| B | A + OCR (image chunks with only `ocr_text` populated) | Runnable: configure `OCR_PROVIDER=tesseract`, `VLM_PROVIDER=""` |
| C | A + VLM descriptions (image chunks with only `vlm_description` populated) | Runnable: configure `VLM_PROVIDER=ollama`, `OCR_PROVIDER=""` |
| D | A + OCR + VLM | Runnable: configure both providers (Phase 4 default combined behavior) |
| E | A + tables | Already included in "A" as implemented here (tables were never excluded from the Phase 1-3 corpus) — this row is not separately distinguishable from A given this project's table-indexing history; noted rather than silently dropped |
| F | A + transcript chunks | Runnable: include audio-ingested documents in the corpus |
| G | Full multimodal textual representation (D + E + F together) | Runnable: the Phase 4 default configuration with all providers enabled |
| H | Caption/OCR retrieval (row G) | Implemented — this is what row G above measures |
| I | Direct visual embedding retrieval | **Not implemented** — no CLIP/visual-embedding model was added (see docs/architecture/multimodal.md "Visual Embeddings — Explicitly Not Implemented") |
| J | Hybrid visual + textual retrieval | **Not implemented** — depends on I |

**Not yet run**: no VLM/OCR/Whisper model was available in this
environment (see docs/research/reproducibility.md "Known Environment
Dependency (Phase 4)"), so rows B/C/D/F/G above have not actually been
executed against real model output — only their configuration mechanism
is implemented and confirmed wired end-to-end (mocked providers, see the
Phase 4 dev dataset). No results are reported until they are.

## Phase 5 Study Engine Ablation Rows

`StudyEngineServiceConfig` (spec section 30) mirrors
`GenerationServiceConfig`'s toggle pattern exactly — three ablation
toggles, each defaulting to `True` so the full pipeline runs unless a
caller/experiment explicitly disables a stage:

| Toggle | Adds/removes |
|---|---|
| `enable_sufficiency_check` | evidence-sufficiency gate (stage A vs. B below) |
| `enable_citation_validation` | citation grounding/rejection during item validation |
| `enable_contradiction_check` | `LexicalContradictionChecker` pass over the evidence set |

| Configuration | Adds | Status |
|---|---|---|
| A | Retrieved evidence + plain generation (all three toggles off) | Runnable via `StudyEngineServiceConfig(enable_sufficiency_check=False, enable_citation_validation=False, enable_contradiction_check=False)` — items are still structurally validated (empty fields, MCQ option integrity), only the *grounding-requires-a-valid-citation* rule and the sufficiency abstention gate are lifted |
| B | A + evidence sufficiency check | `enable_sufficiency_check=True`, others off |
| C | B + citation validation (grounding requirement) | `enable_sufficiency_check=True`, `enable_citation_validation=True` |
| D | C + contradiction checking | All three toggles on (the default `StudyEngineServiceConfig()`) |
| E | Full grounded study generation across every mode | Row D, run once per mode (summary/explain/compare/quiz/mcq/flashcards) |

Applies identically to every study mode — the same `StudyEngineService`
instance and config drive all six `generate_*`/`summarize`/`explain`/
`compare` methods, so an experiment script would sweep modes × rows the
same way `run_generation_experiment.py` sweeps retrieval modes × rows A-G.

**Not yet run**: no experiment runner script was written to execute this
ladder against a real model (same status as the Phase 3/4 ladders above);
only the toggle mechanism itself is implemented and unit-tested
(`tests/study/test_service.py`). No results are reported until measured.

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
