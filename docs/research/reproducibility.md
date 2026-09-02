# Reproducibility

This document records the environment and parameters needed to reproduce any
experiment run against this project. It is updated as components are
actually implemented — parameters listed as "baseline (planned)" are the
values we intend to use once that component exists, not results already
produced.

## Environment (Phase 0)

| Item | Value |
|---|---|
| OS assumption | macOS / Linux, local-first |
| Python version | 3.12 (pinned via `uv`, see `backend/.python-version`) |
| Node version | 20+ (developed against Node 26) |
| Package managers | `uv` (backend), `pnpm` (frontend) |

## Model Configuration (baseline, planned)

| Parameter | Value |
|---|---|
| Embedding model | `BAAI/bge-small-en-v1.5` |
| Embedding dimension | 384 |
| Reranker model | `cross-encoder/ms-marco-MiniLM-L-6-v2` |
| HyDE model | DeepSeek-R1 1.5B (or equivalent locally runnable model) |
| Generation model | DeepSeek-R1 8B via Ollama (replaceable) |
| Chunk size | ~512 tokens (structure-aware baseline) |
| Chunk overlap | TBD — recorded here once chunking is implemented |
| Retrieval top-K (BM25) | TBD |
| Retrieval top-K (FAISS) | TBD |
| RRF k | 60 |
| Reranker top-K | TBD |
| Generation temperature / seed | TBD — recorded once generation is implemented |

## Dataset Versions

None yet. Evaluation datasets will be versioned (filename or hash) and
recorded here once introduced under `evaluation/datasets/`.

## Experiment Configuration Policy

Every experiment must be run from an explicit, checked-in configuration
(not parameters buried in source code) so it can be rerun later with the
same settings. Configuration files will live under
`evaluation/experiments/` once the evaluation harness exists (see
[docs/research/evaluation-plan.md](evaluation-plan.md)).

No experimental results are recorded in this document, or anywhere else in
the repository, until the corresponding run has actually been executed.
