# Roadmap

Development proceeds phase-by-phase. Each phase is implemented, tested, and
documented before the next one starts — no jumping ahead (see project rules
in the repository's development instructions).

| Phase | Name | Status |
|---|---|---|
| 0 | Project foundation | ✅ Complete |
| 1 | Document ingestion | ✅ Complete |
| 2 | Baseline retrieval | Not started |
| 3 | Grounded generation | Not started |
| 4 | Explainability | Not started |
| 5 | Multimodal retrieval | Not started |
| 6 | Study engine | Not started |
| 7 | Improved retrieval | Not started |
| 8 | Evidence sufficiency + abstention | Not started |
| 9 | Contradiction detection | Not started |
| 10 | Frontend integration | Not started |
| 11 | Evaluation + ablation | Not started |
| 12 | Security + hardening | Not started |
| 13 | Final experiments | Not started |
| 14 | Research documentation | Not started |

Phase 0 scope: repository structure, backend/frontend scaffolding, tooling
(lint/type-check/test), `/health` endpoint, minimal frontend shell, and the
documentation set (architecture, API, database, evaluation plan, ablation
plan, reproducibility, security, ADRs). No RAG components (BM25, FAISS,
HyDE, RRF, reranking, generation, multimodal processing, study engine) are
implemented in Phase 0.

Phase 1 scope: file validation, SHA-256 hashing + duplicate detection,
Docling-backed parsing behind a `DocumentParser` interface, a canonical
document/block model independent of Docling, structure-aware chunking
(~512-token EduRAG baseline, configurable overlap as an implementation
choice), SQLite persistence for `documents`/`chunks`, the
`POST /documents/upload` / `GET /documents` / `GET /documents/{id}` API,
and a minimal frontend upload flow — see
[docs/architecture/ingestion.md](architecture/ingestion.md) for the full
design, including documented known limitations (PDF fidelity on tiny
documents, HTML image byte extraction, formula enrichment disabled). No
BM25, FAISS, embeddings, HyDE, RRF, reranking, or LLM generation are
implemented in Phase 1 — those are Phase 2+.
