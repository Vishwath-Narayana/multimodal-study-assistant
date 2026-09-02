# Roadmap

Development proceeds phase-by-phase. Each phase is implemented, tested, and
documented before the next one starts — no jumping ahead (see project rules
in the repository's development instructions).

| Phase | Name | Status |
|---|---|---|
| 0 | Project foundation | ✅ In progress (this commit series) |
| 1 | Document ingestion | Not started |
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
