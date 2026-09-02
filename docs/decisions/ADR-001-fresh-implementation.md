# ADR-001: Fresh Implementation, Not a Fork

## Status
Accepted

## Context
This project reproduces the baseline architecture described in the EduRAG
research paper (hybrid BM25 + FAISS retrieval, HyDE, RRF, cross-encoder
reranking, grounded generation, explainability). An existing open-source
implementation could theoretically be forked to save time.

## Decision
This repository is a **new, independent implementation**. We may inspect
existing open-source RAG/multimodal-study-assistant projects for reference
and reuse established libraries (Docling, FAISS, sentence-transformers,
etc.), but the architecture, integration, code organization, evaluation
harness, and project-specific extensions are our own.

## Consequences
- No upstream repository history, license obligations, or coupling to
  inherit.
- Slower initial progress than forking, in exchange for full control over
  architecture decisions and the ability to make research-driven changes
  without fighting an inherited codebase.
- If code is ever copied from a reference implementation, its license must
  be checked, attribution preserved, and the reused component + its
  modifications documented (see project dependency/open-source policy).
