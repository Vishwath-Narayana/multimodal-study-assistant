# Reference paper: EduRAG

This document records the architecture characteristics and reported
metrics of the project's principal reference paper — **"EduRAG: A
Multimodal Explainable RAG System With Deterministic Token Grounding"**
(IEEE Access, 2026) — for use as a baseline/reference point only.

**These are REFERENCE VALUES ONLY.** They were not measured by this
project. This system's own measured results live in
[PHASE_7_EVALUATION_REPORT.md](PHASE_7_EVALUATION_REPORT.md) and are kept
in a separate section from anything in this file. Nothing in this project
claims to reproduce EduRAG's reported numbers — the exact experimental
conditions (dataset, hardware, model checkpoints) were not reproduced, so
any resemblance in architecture is not evidence of matching performance.
Where this document is silent on a paper detail, that detail was not
available to this project (no access to EduRAG's own codebase, dataset,
or supplementary material beyond the published paper) and is left blank
rather than guessed.

## Architecture characteristics (as referenced by this project's design)

- Multimodal document ingestion (text, tables, images/diagrams, audio
  transcripts) with structure-aware chunking.
- Hybrid retrieval: sparse (BM25) + dense (embedding-based) retrieval,
  fused via Reciprocal Rank Fusion (RRF).
- HyDE (Hypothetical Document Embeddings) query expansion.
- Cross-encoder reranking of the fused candidate pool.
- Grounded generation with deterministic token-level grounding (matching
  hierarchy: exact / stem / substring / ungrounded).
- Evidence sufficiency checking and abstention when evidence is
  insufficient.
- Citation extraction and validation against retrieved evidence.
- Contradiction/source-consensus checking across evidence chunks.

## Configuration values this project adopted as baseline choices

These are architecture choices this project's own design documents (Phase
0-6 `docs/architecture/*.md`) attribute to EduRAG or treat as its baseline,
carried forward unchanged into Phase 7's evaluation:

| Component | Value | Source in this repo |
|---|---|---|
| Chunk target size | ~512 tokens | `docs/architecture/ingestion.md` |
| RRF constant `k` | 60 | `app/retrieval/rrf.py` |
| Embedding model | `BAAI/bge-small-en-v1.5` | `app/core/config.py` |
| Reranker model | `cross-encoder/ms-marco-MiniLM-L-6-v2` | `app/core/config.py` |
| Token grounding threshold | 0.8 (grounded cutoff) | `app/generation/token_grounding.py` |
| Chunk attribution weighting | 0.7 × relevance + 0.3 × lexical overlap | `app/generation/attribution.py` |

Chunk overlap, the evidence-sufficiency thresholds, and the generation
temperature/max-tokens are documented in this repo's own architecture docs
as **implementation choices**, not values taken from EduRAG — see
`app/core/config.py`'s inline comments for exactly which each is.

## Reported metrics

Not reproduced here. This project does not have independently verified
access to EduRAG's exact reported metric values under exactly matched
conditions, and per the Phase 7 absolute rule ("no fabricated results"),
a number is not written into this table unless it can be attributed to a
specific, checkable source. Any comparison drawn in
`PHASE_7_EVALUATION_REPORT.md` against "the EduRAG-style baseline" refers
to the **architecture-level baseline** described above (this project's own
unmodified Phase 2-6 implementation), not to EduRAG's own published
numbers — see that report's "Research Claims" framing and its repeated use
of "EduRAG-inspired baseline configuration" rather than "EduRAG's
results."

## How this document is used in Phase 7

- `docs/evaluation/PHASE_7_EVALUATION_REPORT.md` treats the *architecture*
  in this document as the design lineage for the retrieval pipeline under
  test — hybrid BM25+dense retrieval, RRF fusion, HyDE, cross-encoder
  reranking, deterministic grounding.
- No numeric value in this document is copied into that report's results
  tables. Every number in the results tables is either measured in this
  environment (labeled accordingly) or marked NOT MEASURED / NOT
  AVAILABLE.
