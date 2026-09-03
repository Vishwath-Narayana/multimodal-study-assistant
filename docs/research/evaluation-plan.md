# Evaluation Plan

Status: **retrieval metrics + harness implemented (Phase 2)**; **generation
and trust/grounding metric functions implemented (Phase 3)**, but not yet
run against real model output (see "Generation Metrics" below);
multimodal/research metrics remain **plan only**, pending Phase 5+.

## Retrieval Metrics — implemented

`backend/app/retrieval/evaluation/metrics.py`, unit-tested with
hand-computed examples (`tests/retrieval/test_metrics.py`):

- MRR (Mean Reciprocal Rank)
- Recall@1
- Recall@5
- Precision@5 (Precision@K generalized, K configurable)
- Hit Rate@5

### Phase 2 dev-benchmark results (actually run, not hand-pasted)

Produced by `backend/scripts/run_retrieval_experiment.py` against the
6-query dev dataset (`backend/app/retrieval/evaluation/dataset.json`, built
on the Phase 1 fixtures). Real BM25 + real `BAAI/bge-small-en-v1.5` +
`IndexFlatIP` FAISS + real `cross-encoder/ms-marco-MiniLM-L-6-v2`; HyDE
**mocked** (fixed canned passage, unrelated to any query — no Ollama
available in this environment). See
[docs/research/reproducibility.md](reproducibility.md) for the exact run
configuration.

| Mode | MRR | Recall@1 | Recall@5 | Precision@5 | Hit Rate@5 |
|---|---|---|---|---|---|
| `bm25` | 0.444 | 0.139 | 0.528 | 0.267 | 0.667 |
| `dense` | 0.722 | 0.278 | 0.778 | 0.400 | 0.833 |
| `dense_hyde` (mocked HyDE) | 0.333 | 0.056 | 0.194 | 0.100 | 0.500 |
| `hybrid_rrf` | 0.708 | 0.278 | 0.639 | 0.333 | 0.833 |
| `hybrid_rrf_hyde` (mocked HyDE) | 0.583 | 0.194 | 0.472 | 0.233 | 0.833 |
| `full_baseline` (mocked HyDE) | 0.750 | 0.250 | 0.833 | 0.433 | 0.833 |

**Caveats — read before drawing any conclusion from these numbers**:
- 6 queries is a dev smoke-test, not a statistically meaningful benchmark
  — do not treat these as final baseline numbers.
- Every `*_hyde` row used a **mocked, query-independent** HyDE passage
  (no Ollama in this environment), so the drop those rows show versus
  their non-HyDE counterparts (e.g. `dense_hyde` vs. `dense`) reflects the
  mock being irrelevant to the query, **not** a real measurement of HyDE's
  effect — expect these rows to change substantially with real HyDE
  generation. This run exists to prove the pipeline is wired correctly end
  to end, not to evaluate HyDE.
- `full_baseline`'s reranker still received real (non-mocked) fused
  candidates and scored them for real; only the HyDE *text* is mocked, so
  its numbers are more meaningful than the two `*_hyde`-only rows, though
  still on only 6 queries.
- These numbers exist because the run above was actually executed — they
  are never to be edited by hand; re-run
  `scripts/run_retrieval_experiment.py` to reproduce or update them.

## Generation Metrics — implemented, not yet run against real model output

`backend/app/generation/evaluation/metrics.py`, unit-tested with
hand-computed examples (`tests/generation/test_evaluation_metrics.py`):

- Token F1 — implemented (`token_f1`).
- ROUGE-L — implemented (`rouge_l`, from-scratch LCS-based, no `rouge-score` dependency).
- BERTScore F1 — **not implemented**; `bertscore_f1` raises `NotImplementedError`
  (requires the optional `bert-score` dependency, not installed).

None of these have been run against real model output: the Phase 2 dev
dataset (`app/retrieval/evaluation/dataset.json`) has relevance judgments
but no reference *answer* text to score generated answers against — see
[docs/architecture/generation.md](../architecture/generation.md)
"Evaluation" and "Known Limitations".

## Trust / Grounding Metrics — implemented, not yet run against real model output

`compute_trust_metrics` in the same module:

- Citation validity rate — implemented.
- Unsupported claim rate — implemented (claim has no supporting chunk, or
  its grounding ratio is below a configurable threshold).
- Grounded-question rate / grounded-answer rate — implemented.
- Correct-abstention rate / false-answer rate — implemented, but only
  computable when a gold `answerable` label is supplied per example (no
  such labeled dataset exists yet).
- Faithfulness — **not implemented as a distinct metric**; token grounding
  ratio and unsupported-claim rate are this project's operational proxies
  for it (see docs/architecture/generation.md "Token Grounding" for why a
  separate faithfulness score was not added on top of those).

`backend/scripts/run_generation_experiment.py` computes the subset of these
that don't need a reference answer (citation validity rate, mean token
grounding ratio, conflict rate) per ablation stage, using a mocked
generator by default.

## Multimodal Metrics

- Visual retrieval accuracy
- Table retrieval accuracy
- Diagram retrieval accuracy
- Transcript retrieval accuracy
- Timestamp citation accuracy

## Proposed Research Metrics (for our extensions)

- Contradiction detection precision / recall / F1
- Correct abstention rate
- False-answer rate
- Evidence sufficiency accuracy

## Process

1. Every run uses an explicit configuration (see
   [docs/research/reproducibility.md](reproducibility.md)).
2. Results are written under `backend/experiment-results/<run-id>.json`
   (gitignored — see `app/retrieval/evaluation/runner.py::ExperimentReport`)
   alongside the configuration that produced them. (Earlier drafts of this
   plan referenced `evaluation/experiments/`; the implemented path is
   `backend/experiment-results/`, kept alongside the backend package that
   produces it.)
3. No metric value is written into any document (README, ADRs, papers)
   until the run that produced it exists in `backend/experiment-results/`
   — see the Phase 2 retrieval results table above for the one exception
   this rule allows: numbers copied from an actual run, with its caveats
   stated alongside them.
4. Baseline (reproduced EduRAG) results are recorded separately from
   results including our extensions, so improvements can be attributed
   correctly — see [docs/research/ablation-plan.md](ablation-plan.md).
