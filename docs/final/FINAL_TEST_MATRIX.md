# Final Functional Test Matrix (Phase 9)

Status as of `feature/final-report-demo`, based on `develop` @ `5c58f41`
(Phase 8 merged). Compiled from: the automated test suite (`uv run pytest`,
`pnpm test`), live manual verification against a running backend on
2026-09-04 (documented in `docs/final/PHASE_9_FINAL_REPORT.md` §3), and
code inspection where neither was possible. Only marked **PASS** where
actually verified in this phase or a prior phase's own test suite — never
inferred from "the code looks correct."

Legend: **PASS** verified working · **FAIL** verified broken · **BLOCKED**
verified not runnable here (dependency unavailable) · **NOT AVAILABLE**
feature/dependency not present in this environment · **NOT APPLICABLE**
out of scope for this project.

| Feature | Unit Tested | Integration Tested | E2E Tested | Result | Notes |
|---|---|---|---|---|---|
| Document upload (PDF) | Yes | Yes | Blocked (this env) | PASS (test suite) / BLOCKED (live server) | `backend/tests/ingestion/*`, `tests/security/test_upload_attacks.py`. Live `uvicorn` process crashed during Docling's layout-model load for a real PDF in this sandboxed shell (multiprocessing/semaphore issue observed in the process, not an application exception); the identical code path is exercised in-process by pytest's `TestClient` and passes there. Treated as a sandbox limitation, not an architectural bug — see PHASE_9_FINAL_REPORT.md §11. |
| Document upload (DOCX) | Yes | Yes | Yes | PASS | Verified live: `POST /documents/upload` → `status":"completed"`, 9 chunks from `study_notes.docx`. |
| Document upload (PPTX) | Yes | Yes | Not attempted live | PASS (test suite) | `backend/tests/ingestion/*`. |
| Document upload (HTML) | Yes | Yes | Not attempted live | PASS (test suite) | Magic-byte validation documented as accepted gap for HTML (no reliable signature). |
| Document upload (image) | Yes | Yes | Not attempted live | PASS (test suite) | `app.multimodal.security.validate_image_artifact`. |
| Document upload (audio, faster-whisper) | Yes | Yes | Not attempted live | PASS (test suite) | `faster_whisper` importable in this environment; live real-audio transcription not additionally run in Phase 9. |
| File validation (extension/size/magic-byte) | Yes | Yes | Yes | PASS | `tests/security/test_upload_attacks.py` (18 tests); confirmed live for DOCX. |
| Ingestion → SQLite persistence | Yes | Yes | Yes | PASS | Confirmed live: `GET /documents` lists the uploaded document with correct metadata. |
| Structure-aware chunking | Yes | Yes | Yes | PASS | 9 chunks produced live from the DOCX fixture. |
| Document deletion (cascade) | Yes | Yes | Yes | PASS | Confirmed live: `DELETE /documents/{id}` → 204, subsequent `GET` → 404. |
| BM25 retrieval | Yes | Yes | Yes | PASS | Confirmed live: `POST /retrieval/search` with `mode=bm25` returned ranked, scored results. |
| Dense (FAISS/BGE) retrieval | Yes | Yes | Not attempted live | PASS (test suite) | `sentence_transformers`/`faiss` importable in this environment. |
| Hybrid RRF | Yes | Yes | Not attempted live | PASS (test suite) | Measured in Phase 7 (see Evaluation summary). |
| Cross-encoder reranking | Yes | Yes | Not attempted live | PASS (test suite) | Measured in Phase 7. |
| HyDE | Yes (mocked) | Pipeline-validated (mocked) | No | NOT MEASURED (real model) | `ollama` not installed on PATH in this environment; live `POST /study/summary` with default mode surfaced the real `503 HyDE was requested but no HyDE provider is configured` failure — the failure path itself is verified, not faked. |
| Chat / grounded generation (`/chat/query`) | Yes (schema/routing) | Yes (schema/routing) | Yes (failure path) | PASS (routing/validation) / NOT MEASURED (live generation) | Live: valid request → correct `503 LLM provider 'ollama' ... unreachable`; malformed body → `422` with field-level detail. No live LLM output exists anywhere in this repository. |
| Evidence sufficiency / abstention | Yes | Yes | No (needs LLM path) | PASS (logic) / NOT MEASURED (end-to-end with live LLM) | `HeuristicSufficiencyChecker` unit- and integration-tested; abstention response format verified without a live model call. |
| Citation validation | Yes | Yes | No | PASS (logic) | `tests/security/test_citation_attacks.py` (8 tests) attack fabricated/stale/cross-request ids. |
| Token grounding | Yes | Yes | No | PASS (logic) | Exercised against fixture answers, not live LLM output. |
| Contradiction detection | Yes | Yes | No | PASS (logic) | `LexicalContradictionChecker`. |
| Multimodal extraction (images, tables) | Yes | Yes | Not attempted live | PASS (test suite) | See `docs/architecture/multimodal.md`. |
| OCR | Yes (mocked provider) | Yes (mocked provider) | No | BLOCKED (real Tesseract) | `tesseract` binary not on PATH in this environment. |
| VLM (image description) | Yes (mocked provider) | Yes (mocked provider) | No | BLOCKED (real VLM) | Requires Ollama + a multimodal model; Ollama not installed. |
| Audio transcription (Whisper) | Yes (interface/fixtures) | Yes (interface/fixtures) | No | NOT MEASURED (real audio) | `faster_whisper` importable but no live transcription run in Phase 9. |
| Study — Summary | Yes | Yes | Yes (failure path) | PASS (routing) / NOT MEASURED (live generation) | Live `POST /study/summary` → correct `503` (HyDE/LLM unreachable), not faked output. |
| Study — Explain | Yes | Yes | No | PASS (routing/schema) | Not separately hit live in Phase 9; same code path as Summary. |
| Study — Compare | Yes | Yes | No | PASS (routing/schema) | |
| Study — Quiz | Yes | Yes | No | PASS (routing/schema) | |
| Study — MCQ | Yes | Yes | No | PASS (routing/schema) | |
| Study — Flashcards | Yes | Yes | No | PASS (routing/schema) | |
| Frontend (document library, chat UI, study UI) | Yes (6 test files, 13 tests) | Partial | No (not exercised via browser in Phase 9) | PASS (unit) / NOT ADDITIONALLY VERIFIED (live browser) | `pnpm test` — 13/13 passed. `pnpm run build` succeeds. Manual browser click-through was not performed in this Phase 9 session; see PHASE_9_FINAL_REPORT.md §11. |
| Security controls (upload/prompt-injection/citation/resource-limits/DB/temp-file) | Yes (70 tests) | Yes | Partial (live 422/503 failure paths only) | PASS | `backend/tests/security/*`, 70/70 passing; see `docs/security/SECURITY_TEST_MATRIX.md` for the full attack→mitigation→test mapping. |
| Backend lint (ruff) | N/A | N/A | N/A | PASS | `uv run ruff check .` — all checks passed. |
| Backend type check (mypy) | N/A | N/A | N/A | PASS | `uv run mypy app` — no issues, 117 source files. |
| Frontend lint (oxlint) | N/A | N/A | N/A | PASS | No errors. |
| Frontend type check (tsc) | N/A | N/A | N/A | PASS | Part of `pnpm run build`. |
| Frontend production build | N/A | N/A | N/A | PASS | `dist/` produced, ~277KB JS / ~19KB CSS gzip-reported sizes unchanged from Phase 8. |

Full backend suite: **505 passed, 4 deselected** (unchanged from Phase 8
end-state — re-run in Phase 9, zero regressions). Frontend: **13 passed**.
