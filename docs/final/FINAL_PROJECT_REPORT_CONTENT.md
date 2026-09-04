# Final Project Report Content

Polished, report-ready content for a university final-year project report.
This is **content to draw from directly**, not a formatted final document
(no cover page, declaration, or institution formatting is applied here).
Every claim below is either implemented-and-verified in this repository or
explicitly marked NOT MEASURED / NOT AVAILABLE — nothing is invented.

## Title

**AI-Powered Multimodal Study Assistant Using Retrieval-Augmented
Generation and Large Language Models**

## Abstract

This project presents a local-first, multimodal retrieval-augmented
generation (RAG) system that lets a student upload their own study
material — PDF, DOCX, PPTX, HTML, images/diagrams, tables, and lecture
audio — and receive grounded, cited answers rather than unsupported
free-text generation. The system implements a hybrid retrieval pipeline
combining BM25 lexical search and dense semantic search (BAAI
bge-small-en-v1.5 embeddings over FAISS), fused with Reciprocal Rank
Fusion and refined with cross-encoder reranking, followed by an
evidence-sufficiency check that allows the system to abstain rather than
answer when retrieved evidence is inadequate. Generated answers carry
deterministic, backend-validated citations and token-level grounding
scores, and multimodal content (images, diagrams, tables, audio
transcripts) is enriched via OCR/vision-language description and
timestamp-aware transcription so it participates in the same retrieval
and citation pipeline as text. A study-assistance layer built on the same
grounded pipeline generates summaries, explanations, comparisons,
quizzes, multiple-choice questions, and flashcards, each traceable to its
source evidence. The system was hardened against a documented set of RAG-
specific security threats — malicious uploads, indirect prompt injection,
citation/provenance forgery, and resource exhaustion — and evaluated with
a real, reproducible pilot retrieval benchmark (BM25 vs. dense vs. hybrid
RRF vs. reranked hybrid) on a small annotated corpus. Retrieval-quality
results and their limitations are reported honestly at pilot scale;
generation-quality, HyDE, and live vision/OCR/transcription evaluation
were not measured in this environment because the required local models
(Ollama, Tesseract) were unavailable, and this gap is stated explicitly
rather than filled with estimated numbers.

## Introduction

Students increasingly accumulate study material across many formats —
lecture PDFs, slide decks, scanned notes, diagrams, and recorded audio —
and generic LLM chat tools answer from general training knowledge rather
than from that material, with no guarantee of correctness and no way to
trace an answer back to its source. This project builds a study assistant
that is explicitly grounded in the student's own uploaded documents,
across text and non-text modalities, with citations the student can
verify and an explicit "I don't have enough evidence" behavior instead of
confident hallucination.

## Motivation

Two observed failure modes motivate this system: (1) general-purpose LLM
chat is not grounded in a specific course's material and cannot cite a
verifiable source for its claims, and (2) students' material is
frequently multimodal (diagrams, tables, recorded lectures), which plain
text-only RAG systems either ignore or degrade badly on. A system that
treats retrieval, grounding, and multimodal evidence as first-class
concerns — rather than bolting citations onto an ungrounded chatbot —
addresses both.

## Problem Statement

Traditional study assistants and generic LLM chat interfaces can
hallucinate confidently, lack verifiable source grounding, struggle to
incorporate a student's own private documents, and handle multimodal
educational material (diagrams, tables, audio) poorly or not at all. This
project addresses these gaps for a bounded, local-first, single-user
study-assistant use case via: student-owned document ingestion across
multiple formats and modalities, hybrid lexical+dense retrieval, grounded
generation with mandatory citation and token-grounding, explicit
evidence-sufficiency-driven abstention, multimodal evidence preservation
and retrieval, and study-content generation tools (summaries, quizzes,
MCQs, flashcards) built on the same grounded pipeline.

## Objectives

- Ingest multimodal educational documents (PDF, DOCX, PPTX, HTML, images,
  audio) into a searchable, provenance-preserving knowledge base.
- Answer student questions with retrieval-grounded, cited responses, and
  abstain explicitly when evidence is insufficient rather than guess.
- Preserve and retrieve multimodal evidence (images/diagrams, tables,
  audio transcripts) as first-class citable content, not as an
  afterthought.
- Generate study aids (summaries, explanations, comparisons, quizzes,
  MCQs, flashcards) traceable back to source evidence.
- Harden the system against RAG-specific security threats (malicious
  uploads, prompt injection, citation forgery, resource exhaustion).
- Evaluate retrieval quality with a reproducible, honestly-scoped
  benchmark and document what could and could not be measured.

## Scope

In scope: single-user, local-first deployment; text/DOCX/PPTX/PDF/HTML/
image/audio ingestion; hybrid retrieval; grounded generation with
citations; six study-generation modes; a pilot retrieval evaluation;
security hardening for the implemented attack surface. Out of scope (by
design, documented as such throughout): authentication/multi-tenancy,
cloud/distributed infrastructure, large-scale academic benchmarking,
direct visual (CLIP-style) embedding retrieval, and any claim of
superiority over the EduRAG reference architecture.

## Literature / Reference System

The retrieval and generation architecture is based on the published
**EduRAG** paper's design (see `docs/evaluation/reference_paper.md`): a
hybrid BM25 + FAISS retrieval pipeline with HyDE query expansion,
Reciprocal Rank Fusion, cross-encoder reranking, grounded generation, and
explainability (citation validation, token grounding). This project does
**not** claim to have invented RAG, hybrid retrieval, BM25, FAISS, HyDE,
RRF, reranking, or explainability techniques — EduRAG is the architectural
reference and baseline, reproduced as a fresh independent implementation
(see `docs/decisions/ADR-001-fresh-implementation.md`), not a fork of
EduRAG's code. **No EduRAG-reported numeric result is reproduced or
compared against under matched conditions anywhere in this project** —
all metrics reported here are this project's own measurements on its own
pilot corpus.

## Existing System

Generic LLM chat interfaces (e.g., consumer chatbots without retrieval
augmentation) and simple single-modality RAG demos that index only plain
text. These do not ground answers in a student's own material, do not
validate citations against actual retrieved evidence, and typically treat
non-text content (images, tables, audio) as unsupported or as a lossy
caption-only representation.

## Proposed System

A modular, local-first multimodal RAG pipeline (architecture detailed in
`docs/final/SYSTEM_ARCHITECTURE.md`) that: ingests and enriches multimodal
documents while preserving original artifacts; retrieves via hybrid
BM25+dense search with RRF fusion and cross-encoder reranking; checks
evidence sufficiency before generating; generates grounded answers with
backend-validated citations and token grounding; detects contradictions
across evidence; and layers study-content generation (six modes) on top
of the same grounded retrieval/citation infrastructure, with security
hardening applied across the whole pipeline.

## System Architecture

See `docs/final/SYSTEM_ARCHITECTURE.md` for the full diagram and
module-by-module detail, verified against the actual `backend/app/`
layout.

## Modules

1. **Ingestion** — upload, validation, Docling parsing, structure-aware
   chunking, SQLite persistence.
2. **Multimodal processing** — OCR + VLM image enrichment, table
   handling, audio transcription (Whisper), original-artifact
   preservation.
3. **Retrieval** — BM25, dense (FAISS/bge-small), HyDE, RRF fusion,
   cross-encoder reranking.
4. **Generation + Explainability** — evidence sufficiency, grounded
   generation, citation validation, token grounding, contradiction
   detection.
5. **Study Engine** — Summary, Explain, Compare, Quiz, MCQ, Flashcards.
6. **Frontend** — document library, chat, study views (React/TypeScript).
7. **Security** — upload/prompt-injection/citation/resource-limit
   hardening.
8. **Evaluation** — reproducible retrieval benchmark and ablations.

## Technology Stack

| Layer | Choice |
|---|---|
| Backend | Python 3.12, FastAPI |
| Frontend | React, TypeScript, Vite, Tailwind CSS |
| Document processing | Docling |
| Embeddings | BAAI/bge-small-en-v1.5 |
| Dense retrieval | FAISS (`IndexFlatIP`) |
| Lexical retrieval | BM25 (`rank-bm25`) |
| Reranking | cross-encoder/ms-marco-MiniLM-L-6-v2 |
| LLM (generation) | Ollama-compatible local model, `deepseek-r1:8b` (configured; not installed in this environment) |
| LLM (HyDE) | Ollama-compatible local model, `deepseek-r1:1.5b` (configured; not installed in this environment) |
| Vision (VLM) | Ollama-compatible multimodal model, optional (not configured/installed in this environment) |
| OCR | Tesseract, optional (not installed in this environment) |
| Audio | Whisper via faster-whisper (installed; live transcription not additionally run in Phase 9) |
| Database | SQLite |
| Backend tooling | uv, pytest, Ruff, mypy |
| Frontend tooling | pnpm, oxlint, vitest |

## Document Ingestion

Upload → magic-byte + extension + size validation → SHA-256 content
hashing (duplicate detection) → Docling parsing → structure-aware
chunking (~512-token target) → SQLite persistence with full provenance
(document, page/section, chunk type). See
`docs/architecture/ingestion.md`.

## Multimodal Processing

Images/diagrams are OCR'd and described by a vision-language model (when
configured); both are merged into a combined searchable text
representation while the **original image bytes are always preserved**
via the `artifacts` table, never replaced by a lossy caption. Tables
retain structured content. Audio is transcribed (Whisper) into
timestamp-aware transcript chunks. See `docs/architecture/multimodal.md`.
**Live VLM/OCR/Whisper generation quality was not measured in this
environment** — Ollama and Tesseract are not installed; the pipeline
logic itself is unit- and integration-tested against fixtures and mocked
providers.

## Retrieval

Six selectable retrieval modes (`bm25`, `dense`, `dense_hyde`,
`hybrid_rrf`, `hybrid_rrf_hyde`, `full_baseline`). See
`docs/architecture/retrieval.md`.

## Hybrid Retrieval

BM25 and dense (FAISS) results are combined via Reciprocal Rank Fusion
(k=60) rather than naive score averaging, which requires no score-scale
normalization between lexical and dense scores.

## RRF

Reciprocal Rank Fusion: `score(d) = Σ 1 / (k + rank_i(d))` across each
retriever's ranked list. Measured on the pilot corpus: hybrid RRF
achieved the highest MRR (0.854) of all tested configurations (see
"Retrieval Results" below).

## HyDE

Hypothetical Document Embeddings — a small local LLM generates a
hypothetical answer passage, which is then embedded and used for dense
retrieval instead of the raw query. **Not measured with a real model** in
this environment (Ollama unavailable); Phase 7 validated only the
pipeline plumbing with a mocked HyDE call, explicitly never reported as a
performance number.

## Reranking

A cross-encoder (`cross-encoder/ms-marco-MiniLM-L-6-v2`) rescoring the
fused candidate list. Measured on the pilot corpus: reranking **improved
Recall@5** (0.681 → 0.764) and precision@5, but **reduced MRR** (0.854 →
0.778) relative to hybrid RRF alone — see "Ablation Results" for the
trade-off discussion.

## Grounded Generation

`GenerationService` constructs a prompt that treats retrieved evidence
strictly as data (never as instructions), calls a local LLM via Ollama,
and never fabricates an answer when evidence is judged insufficient — an
abstention response is returned instead, with no model call. See
`docs/architecture/generation.md`. **Live generation output quality was
not measured** in this environment; the failure path (`503`, LLM
unreachable) was verified live and is the honest, correct behavior when
no local LLM is running.

## Explainability

Deterministic citation validation (only chunk ids actually present in the
current request's evidence are accepted), token-level grounding (exact /
stem / substring match between answer tokens and evidence text), and
lexical contradiction detection across evidence chunks.

## Citation Validation

`DeterministicCitationValidator` — backend-controlled, per-request; never
trusts a chunk id supplied by model output. Attacked directly with 8
dedicated security tests (fabricated id, cross-request id, stale id, id
absent from evidence) — all correctly rejected.

## Token Grounding

Matches each answer token/claim back to the evidence text that supports
it, producing a `grounding_ratio` and per-claim grounding rather than a
single opaque confidence score.

## Evidence Sufficiency

A heuristic check (`HeuristicSufficiencyChecker`, chunk count + score
thresholds) run before any LLM call. When evidence is judged insufficient,
the system returns a fixed abstention response and citations/grounding
are empty/null — the LLM is never invoked for an abstention, so an
abstention can never itself hallucinate.

## Study Engine

Six modes — Summary, Explain, Compare, Quiz, MCQ, Flashcards — built
entirely on top of the existing retrieval and explainability
infrastructure (no separate retrieval or grounding logic). Every
generated study item records `source_chunk_ids` for traceability. See
`docs/architecture/study-engine.md`.

## User Interface

React/TypeScript/Vite/Tailwind frontend: document library (upload, list,
delete), chat interface with citation/evidence display, and study-mode
views. All API-sourced content renders as plain React text (auto-escaped,
no `dangerouslySetInnerHTML`).

## Evaluation Methodology

A pilot retrieval benchmark was built and run against real components
(real BM25, real BGE-small embeddings + FAISS, real RRF, real
cross-encoder reranker) — not simulated or estimated. See
`docs/evaluation/PHASE_7_EVALUATION_REPORT.md`,
`docs/evaluation/DATASET.md`, `docs/evaluation/REPRODUCIBILITY.md`.
Generation, HyDE, and multimodal (VLM/OCR/live transcription) evaluation
were explicitly **NOT MEASURED** — required local dependencies (Ollama,
Tesseract) were unavailable in the evaluation environment, and this gap
is stated rather than filled with an estimate.

## Pilot Dataset

`pilot_v1`: 3 real documents (built from actual Phase 1 ingestion output,
one real subject, 3 source formats), 23 real ingested chunks, 14
questions (12 answerable, 2 deliberately unanswerable). Gold evidence
chunk ids were derived by actually running ingestion and validating
against real output, never hand-typed. See
`evaluation/datasets/pilot_v1.json` and `docs/evaluation/DATASET.md`.

## Retrieval Results

Measured on the pilot corpus, 12 answerable questions, top_k=5 (from
`evaluation/results/run_baseline_20260904T032025Z/retrieval_comparison.csv`
— verified against the repository's own result file; these figures match
what was independently supplied for this report, with no discrepancy
found):

| Configuration | MRR | Recall@5 | Precision@5 | nDCG@5 | Hit Rate@5 |
|---|---|---|---|---|---|
| BM25 only | 0.667 | 0.611 | 0.383 | 0.590 | 0.833 |
| Dense (BGE) only | 0.806 | 0.708 | 0.417 | 0.685 | 0.917 |
| BM25+Dense, simple score fusion | 0.722 | 0.611 | 0.383 | 0.622 | 0.833 |
| Hybrid RRF (BM25+Dense, k=60) | 0.854 | 0.681 | 0.433 | 0.706 | 0.917 |
| Hybrid RRF + cross-encoder reranker | 0.778 | 0.764 | 0.467 | 0.723 | 0.917 |

**Interpretation** (technically precise, not overstated):
- Hybrid RRF achieved the highest MRR (0.854) on the pilot corpus.
- Hybrid RRF + reranking achieved the highest Recall@5 (0.764) and
  Precision@5 (0.467).
- Reranking improved Recall@5 and Precision@5 but reduced MRR relative to
  hybrid RRF alone — a genuine trade-off (reranking tends to surface more
  relevant items lower in a longer list at some cost to top-1 rank
  quality on this corpus), not a case of one configuration being
  strictly "better" than the other.
- A paired Wilcoxon signed-rank test (n=12) found **none** of these
  differences statistically significant at α=0.05 (p=0.75 for MRR,
  p=0.25 for Recall@5; see `statistical_analysis.json`). The pilot
  corpus is too small to support a broad, generalizable performance
  claim — these are directional, pilot-scale observations only.
- Reranking cost ~4.6× the mean per-query latency of hybrid RRF alone
  (8.9ms → 41.1ms), still well within an interactive budget at this
  corpus size.

## Ablation Results

**Chunking experiment** (whitespace token-count approximation vs. real
BGE subword tokenization): a BGE token-inflation ratio of ~2.19× was
observed (BGE subword tokens vs. whitespace-token estimate), but **no
pilot chunk exceeded the 512-token chunking threshold under either
counting method**, so token-aware chunking produced **no measurable
retrieval difference** on this corpus (identical metrics under both
configurations) and was therefore not adopted. This is reported as a
valid negative result: the inflation ratio is real and worth knowing
about at larger chunk sizes or larger documents, but it did not manifest
as a retrieval-quality problem on this specific pilot corpus.

## Failure Analysis

8 of 12 answerable questions (67%) showed at least one retrieval failure
somewhere in the pipeline sweep, all attributed to the single category
`chunk_boundary_or_ranking_problem` (gold evidence split across chunk
boundaries, or ranked below the cutoff) — no failure was attributed to a
parsing or indexing bug. See
`evaluation/results/run_baseline_20260904T032025Z/failures.json`.

## Security

Phase 8 audited the complete Phase 0–7 system against RAG-specific and
conventional web-application attack classes and produced 15 findings
(`F1`–`F15` in `docs/security/SECURITY_AUDIT.md`), of which 9 required and
received a code-level fix or new control (magic-byte upload validation,
4 resource ceilings, temp-file cleanup on failure paths, prompt-marker
neutralization, log-only injection detection, and 3 new global exception
handlers plus security response headers); the remaining findings were
informational or accepted-by-design (no auth, by scope). 70 new
deterministic security tests were added under `backend/tests/security/`,
and the full backend suite grew to 505 passed / 4 deselected with zero
regressions. One dependency vulnerability remains: `transformers`
CVE-2026-9856, with a verified-unreachable exploit path in this
application (the vulnerable function is never called), pending an
upstream `docling-ibm-models` pin update. See
`docs/security/PHASE_8_SECURITY_REPORT.md` and `SECURITY_TEST_MATRIX.md`.
Residual risks — prompt injection cannot be guaranteed eliminated, no
authentication/multi-tenant isolation exists (by design) — are stated
explicitly, not hidden.

## Testing

Backend: 505 passed, 4 deselected (`uv run pytest -q`), including 70
security tests; `ruff check .` all checks passed; `mypy app` no issues
across 117 source files. Frontend: 13 passed (`vitest`); `oxlint` no
errors; `tsc -b && vite build` succeeds. All re-verified in Phase 9 with
zero regressions against the Phase 8 end-state.

## Results Discussion

The system's retrieval layer demonstrably works end-to-end on real
components and shows a genuine, if pilot-scale, trade-off between hybrid
RRF (best top-rank quality) and reranking (best recall/precision) that
matches the expected behavior of these techniques from the literature.
Generation-side quality (faithfulness of live LLM answers, citation
validity against actual model output, real HyDE contribution, live
multimodal model quality) remains unmeasured pending local model
availability — the system's generation, citation, and grounding *logic*
is thoroughly tested against deterministic fixtures, but no claim is made
about live LLM output quality because none was observed.

## Limitations

- Pilot evaluation corpus is small (3 documents, 23 chunks, 14 questions)
  — not a large academic benchmark; no result here should be read as a
  general performance claim.
- No statistically significant retrieval result was found at this sample
  size (n=12).
- No live generation benchmark exists — Ollama was unavailable throughout
  development and Phase 9 validation.
- HyDE was never measured with a real model.
- VLM, OCR, and live transcription evaluation gaps — Tesseract and a
  configured VLM were unavailable; faster-whisper is installed but not
  additionally exercised live in Phase 9.
- No direct visual (CLIP-style) embedding retrieval — image chunks are
  retrieved via their derived text representation only.
- Single-user, local-first deployment; no authentication or multi-tenant
  isolation.
- Security mitigations reduce, but do not eliminate, prompt injection and
  document-poisoning risk — no prompt-engineering or detection layer can
  guarantee an LLM is never influenced by adversarial context text.

## Future Work

- Run the full retrieval + generation + multimodal benchmark once Ollama,
  Tesseract, and a configured VLM are available, on a larger annotated
  corpus, as a separate controlled experiment (explicitly not auto-run in
  this phase — see the Phase 9 brief's "Optional Full Benchmark" rule).
  Live LLM output would need to be substituted for the empirical failures
  at that time, and any new results would supersede — not silently
  overwrite — this pilot's numbers.
- Direct visual (CLIP-style) embedding retrieval for images/diagrams.
- Authentication and multi-tenant isolation, if the deployment scope ever
  changes from single-user/local-first.
- Statistically powered retrieval evaluation (larger n) to move beyond
  directional signals.
- Live adversarial-model testing of prompt-injection mitigations (this
  phase's security testing was deterministic/unit-level, not against a
  live LLM's actual susceptibility).

## Conclusion

This project delivers a modular, multimodal, local-first RAG study
assistant with a real, measured hybrid retrieval pipeline, deterministic
grounding/citation/explainability infrastructure, a study-content
generation layer built on that same infrastructure, and security
hardening against a documented RAG-specific threat model. Its
retrieval-quality claims are honestly scoped to a small pilot benchmark
with no claim of statistical significance or superiority over the EduRAG
reference architecture, and every capability that could not be measured
in this environment (live generation, HyDE, VLM/OCR/transcription
quality) is stated as such rather than estimated.
