# Roadmap

Development proceeds phase-by-phase. Each phase is implemented, tested, and
documented before the next one starts — no jumping ahead (see project rules
in the repository's development instructions).

| Phase | Name | Status |
|---|---|---|
| 0 | Project foundation | ✅ Complete |
| 1 | Document ingestion | ✅ Complete |
| 2 | Baseline retrieval | ✅ Complete |
| 3 | Grounded generation + explainability | ✅ Complete |
| 4 | ~~Explainability~~ (merged into Phase 3) | — |
| 5 | Multimodal retrieval | ✅ Complete |
| 6 | Study engine | ✅ Complete |
| 7 | Improved retrieval | Not started |
| 8 | ~~Evidence sufficiency + abstention~~ (merged into Phase 3) | — |
| 9 | ~~Contradiction detection~~ (merged into Phase 3) | — |
| 10 | Frontend integration | ✅ Complete |
| 11 | Evaluation + ablation | 🟡 Partial (retrieval evaluation/ablation complete; generation-dependent evaluation blocked — see below) |
| 12 | Security + hardening | Not started |
| 13 | Final experiments | Not started |
| 14 | Research documentation | Not started |

**Phase 3 scope note**: the Phase 3 implementation brief this phase was
built against bundled explainability, evidence sufficiency/abstention, and
contradiction detection into "Phase 3" as one delivered unit, rather than
the four separate rows (3/4/8/9) this table originally listed. Rows 4, 8,
and 9 are struck through here rather than silently deleted, so the
renumbering is visible; no phase after Phase 3 was pulled forward or
skipped — only the finer-grained split of generation-adjacent work was
collapsed.

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

Phase 2 scope: BM25 (`rank-bm25`), dense retrieval (`BAAI/bge-small-en-v1.5`
+ FAISS `IndexFlatIP`), Reciprocal Rank Fusion (k=60), HyDE query expansion
(Ollama-backed, off by default, mockable), cross-encoder reranking
(`cross-encoder/ms-marco-MiniLM-L-6-v2`), six independently selectable
retrieval modes (`bm25`/`dense`/`dense_hyde`/`hybrid_rrf`/
`hybrid_rrf_hyde`/`full_baseline`), a `RetrievalService` orchestrator with a
full per-query trace, the `POST /retrieval/search` research/debug endpoint,
evaluation metrics (MRR/Recall@1/Recall@5/Precision@5/Hit Rate@5) and an
experiment runner against a small dev benchmark built on the Phase 1
fixtures — see [docs/architecture/retrieval.md](architecture/retrieval.md).
No answer generation, citations, grounding, contradiction detection,
evidence sufficiency, abstention, study engine, or multimodal/audio
retrieval are implemented in Phase 2 — those are Phase 3+.

Phase 3 scope: evidence sufficiency / abstention (heuristic: chunk count +
lexical overlap + optional reranker score), grounded LLM generation
(`Generator`/`OllamaGenerator`, DeepSeek-R1 8B baseline via Ollama, mockable
in tests), a strict grounded prompt keeping system instructions/evidence/
question in separate labeled sections, `[chunk:<id>]` citation extraction +
deterministic validation against the retrieved evidence set, deterministic
EduRAG-style chunk attribution (0.7 x cross-encoder relevance + 0.3 x
lexical overlap), EduRAG-style token grounding (exact/stem/substring/
ungrounded matching hierarchy), claim-level grounding, lightweight lexical
contradiction/source-consensus checking, the `POST /chat/query` endpoint,
generation/trust evaluation metrics (Token F1, ROUGE-L; BERTScore left
unimplemented — optional dependency not installed), and ablation support
for the full A–G stage ladder — see
[docs/architecture/generation.md](architecture/generation.md). No quizzes,
flashcards, summaries-as-a-tool, comparison tools, audio/Whisper, new
multimodal ingestion, image understanding, advanced conversation memory, or
chat frontend are implemented in Phase 3 — those remain later phases. Phase
1 ingestion and Phase 2 retrieval are unchanged by Phase 3 (including the
documented BGE chunking/truncation issue, left as-is per that issue's own
disposition).

Phase 5 scope (implemented as "Phase 4" against the implementation brief
this work was built from — see
[docs/architecture/multimodal.md](architecture/multimodal.md)'s numbering
note): VLM-based image/diagram description (`OllamaVisionProvider`,
optional/config-driven) and OCR (`TesseractOCRProvider`, optional), with
original visual evidence always preserved separately from derived
descriptions; table-aware structured representation helpers on top of
Phase 1's existing table extraction; documented (not fabricated) equation
representation limitations; audio ingestion with Whisper transcription
(`WhisperTranscriptionProvider`, optional) and timestamp-aware transcript
chunking (`BlockType.TRANSCRIPT`); a new `artifacts` provenance table
(additive DB migration, no data loss); integration of all of the above
into the existing Phase 2 BM25/FAISS indexing (no second retrieval
system, no new retrieval mode); multimodal evidence/citation fields
propagated through the unchanged Phase 3 `GenerationService` into
`POST /chat/query`; `GET /documents/{id}/artifacts` and
`GET /chunks/{id}`; multimodal evaluation metrics and a small mocked-
provider dev dataset. No quizzes, flashcards, study-plan generation,
advanced tutoring, new chat UI, authentication, deployment, or direct
visual (CLIP-style) embeddings are implemented in Phase 5 — see
docs/architecture/multimodal.md "Visual Embeddings" and "Known
Limitations".

Phase 6 scope (implemented as "Phase 5 — Study Engine" against the
implementation brief this work was built from — see
[docs/architecture/study-engine.md](architecture/study-engine.md)): a
`StudyEngineService` orchestrating six grounded study modes (summary,
explain, compare, quiz, mcq, flashcards) on top of the unchanged Phase 2
`RetrievalService` and Phase 3 sufficiency/citation/contradiction
components (no second retrieval or grounding pipeline); dedicated
per-mode prompts and a new JSON-from-LLM parsing/validation layer
(`app.study.parsing`/`app.study.validation`) since no such helper existed
before; deterministic MCQ/quiz/flashcard/comparison structural validation
and within-batch duplicate detection; a new `study_items` persistence
table (additive `CREATE TABLE`, no migration needed); six
`POST /study/{summary,explain,compare,quiz,mcq,flashcards}` endpoints;
study evaluation metric/dataset interfaces. No polished frontend/study UI,
authentication, deployment, learner analytics, spaced repetition,
gamification, or autonomous tutoring agents are implemented in Phase
6 — see docs/architecture/study-engine.md "Known Limitations".

Phase 10 scope (implemented as "Phase 6 — Application/UI" against the
implementation brief this work was built from — see
[docs/architecture/frontend.md](architecture/frontend.md)): a complete
React/TypeScript/Vite/Tailwind student-facing application on top of the
unchanged Phase 1-5 backend — Dashboard, Document Library (upload/list/
delete), a per-document view with quick actions, a global RAG Chat, and a
unified Study workspace (Summary/Explain/Compare/Quiz/MCQ/Flashcards); a
central typed API client (`frontend/src/lib/api/`); an evidence/citation
UI exposing modality (text/image/diagram/table/transcript), page/section/
timestamp, and validation status for every answer, with an explicit
"Insufficient evidence" state when abstained; loading/error/empty states
throughout; responsive (mobile/tablet/desktop) layout; keyboard/focus-
visible accessibility. Two minimal, additive backend endpoints were added
because the UI could not function without them (`DELETE /documents/{id}`
for the document library's delete action, `GET /artifacts/{id}/file` to
display multimodal evidence images) — see docs/API.md. `feature/
study-engine` was also merged into `develop` during this phase: it had
been fully implemented but never merged, which the frontend needed. No
retrieval/generation/grounding/citation/study-engine algorithm was
modified. No authentication, deployment, learner analytics, spaced
repetition, or gamification are implemented in Phase 10 — see
docs/architecture/frontend.md "Known Limitations".

Phase 11 scope (implemented as "Phase 7 — Evaluation & Benchmarking"
against the implementation brief this work was built from — see
[docs/evaluation/PHASE_7_EVALUATION_REPORT.md](evaluation/PHASE_7_EVALUATION_REPORT.md)):
a real evaluation package (`backend/app/benchmarking/`) with a versioned
YAML config system, a reproducibility manifest (git SHA/branch, dataset
stats, seed, real dependency-availability checks), a Phase 7B.1 benchmark
schema, and a small honest pilot dataset (`evaluation/datasets/
pilot_v1.json`, 14 questions built from the real Phase 1 fixtures — no
other real academic corpus was available in this environment, see
[docs/evaluation/DATASET.md](evaluation/DATASET.md)); real, measured
retrieval evaluation and ablation (BM25/dense/simple-fusion/RRF/
reranker, top-k sweep, a controlled chunking experiment) against that
dataset; failure analysis; an evidence-based improvement recommendation
(adopt reranking; chunking change evaluated and explicitly not adopted);
a baseline-vs-final comparison with paired Wilcoxon significance testing
and CPU latency measurement; generated figures/tables; and four new
`docs/evaluation/*.md` documents. One small, additive, backward-
compatible change was made to existing code:
`ChunkingConfig.token_counter` (`app/ingestion/chunking.py`), needed to
run the controlled chunking experiment — no retrieval, generation, or
grounding algorithm was modified. **Generation, HyDE, faithfulness,
citation validity, token grounding on live output, evidence-sufficiency/
abstention, contradiction detection, and real multimodal (VLM/OCR/
transcription) evaluation are NOT MEASURED** in this phase — Ollama,
tesseract, and a real transcription/VLM run are not available in this
environment; see the evaluation report's "Limitations" and "Future Work"
for exactly what remains blocked and how to unblock it. No Phase 1-6
algorithm, endpoint, or UI was modified.
