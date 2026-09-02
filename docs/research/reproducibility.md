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
| Node version | 22+ (pnpm 11 requires Node ≥22.13; developed against Node 26; CI pinned to Node 22) |
| Package managers | `uv` (backend), `pnpm` (frontend) |

## Ingestion Configuration (Phase 1, implemented)

| Parameter | Value | Source |
|---|---|---|
| Document parser | Docling (`docling` PyPI package) | EduRAG baseline |
| Chunk target size | 512 tokens (`CHUNK_TARGET_TOKENS`) | EduRAG baseline ("approximately 512 tokens") |
| Chunk overlap | 50 tokens (`CHUNK_OVERLAP_TOKENS`) | **Implementation choice** — not specified by the baseline paper |
| Token counting | whitespace-split word count | **Implementation choice** — not any specific embedding model's tokenizer; alignment deferred to Phase 2 |
| Document identity | SHA-256 of file bytes, used directly as `document_id` | **Implementation choice** |
| Max upload size | 50MB (`MAX_UPLOAD_SIZE_MB`) | **Implementation choice** |
| Supported formats | pdf, docx, pptx, html, htm (`SUPPORTED_EXTENSIONS`) | **Implementation choice** — EduRAG does not enumerate a fixed format list |
| Formula/equation enrichment | disabled (Docling `do_formula_enrichment=False`) | **Implementation choice** — avoids an additional VLM model download; see docs/architecture/ingestion.md §4 |

All of the above are read from `Settings` (`backend/app/core/config.py`),
overridable via `.env` — never hard-coded inside ingestion logic (PHASE 1
§27 of the project brief).

## Model Configuration (retrieval/generation baseline, planned)

| Parameter | Value |
|---|---|
| Embedding model | `BAAI/bge-small-en-v1.5` |
| Embedding dimension | 384 |
| Reranker model | `cross-encoder/ms-marco-MiniLM-L-6-v2` |
| HyDE model | DeepSeek-R1 1.5B (or equivalent locally runnable model) |
| Generation model | DeepSeek-R1 8B via Ollama (replaceable) |
| Retrieval top-K (BM25) | TBD |
| Retrieval top-K (FAISS) | TBD |
| RRF k | 60 |
| Reranker top-K | TBD |
| Generation temperature / seed | TBD — recorded once generation is implemented |

## Known Environment Dependency (Phase 1)

Docling's default PDF pipeline downloads ML layout-detection and RapidOCR
model weights from Hugging Face / ModelScope on first use (a few tens of
MB, cached under the Python environment afterward). Running PDF ingestion
for the first time — including running the backend test suite for the
first time — requires network access. DOCX/PPTX/HTML parsing use
format-native Docling backends and do not require any model download.

## Dataset Versions

None yet. Evaluation datasets will be versioned (filename or hash) and
recorded here once introduced under `evaluation/datasets/`. Phase 1's test
fixtures (`backend/tests/fixtures/`) are synthetic, generated
deterministically by `backend/scripts/generate_fixtures.py` — not an
evaluation dataset.

## Experiment Configuration Policy

Every experiment must be run from an explicit, checked-in configuration
(not parameters buried in source code) so it can be rerun later with the
same settings. Configuration files will live under
`evaluation/experiments/` once the evaluation harness exists (see
[docs/research/evaluation-plan.md](evaluation-plan.md)).

No experimental results are recorded in this document, or anywhere else in
the repository, until the corresponding run has actually been executed.
