# Submission / Reproducibility Checklist

Verified during Phase 9 (`feature/final-report-demo`, based on `develop`
@ `5c58f41`). Each item below was actually checked, not assumed.

| Item | Status | Notes |
|---|---|---|
| README current | DONE | See `README.md` — updated in Phase 9 to add Phase 5–8 status, evaluation results, security summary, and limitations (previously stopped documenting status at Phase 4/5). |
| Architecture diagram in README | DONE | README §6 retains the baseline diagram; `docs/final/SYSTEM_ARCHITECTURE.md` is linked as the final, complete diagram. |
| Installation instructions work | VERIFIED | `cd backend && uv sync --dev` / `cd frontend && pnpm install` — both environments were already set up and used directly in this phase; commands match what's documented. |
| Backend run command documented | DONE | README §11 — `uv run uvicorn app.main:app --reload`; verified live in Phase 9 (server started, responded on `/health`). |
| Frontend run command documented | DONE | README §11 — `pnpm dev`. |
| Environment variables documented | DONE | `.env.example`, referenced from README §10. |
| Required local models documented | DONE | README §8 technology stack table + `.env.example` comments (Ollama models, Tesseract, Whisper — all marked optional/replaceable). |
| Optional dependencies documented | DONE | Ollama, Tesseract, VLM model are all explicitly optional in `.env.example` and README. |
| Tests documented | DONE | README §12. |
| Evaluation commands documented | DONE | README §13/§14, `docs/evaluation/REPRODUCIBILITY.md`. |
| Security docs linked | DONE | README §"Security" (added in Phase 9) links `docs/security/*`. |
| Screenshots/demo instructions linked | DONE | README links `docs/final/DEMO_SCRIPT.md`. |
| No credentials committed | VERIFIED | `git grep` for common secret patterns and a review of `.env.example` (placeholder values only) found nothing; `.env` itself is gitignored. |
| No private data committed | VERIFIED | `data/`, `models/` are gitignored except `.gitkeep`; the only committed sample documents are the pre-existing, synthetic `backend/tests/fixtures/*` files, not real student material. |
| `.gitignore` correct | VERIFIED | Covers `__pycache__`, `.venv`, `node_modules`, `.env`, `data/raw`/`data/processed` (except `.gitkeep`), `models/*` (except `.gitkeep`), `*.db`/`*.sqlite`/`*.faiss`/`*.index`, experiment-results, logs, OS/editor files. |
| CI green | NOT VERIFIED IN THIS PHASE | `.github/` exists (workflow config present) but Phase 9 did not have access to trigger/inspect a hosted CI run; local equivalents (pytest, ruff, mypy, vitest, oxlint, build) were all run directly and passed — see `docs/final/FINAL_TEST_MATRIX.md`. |
| Repository clean | VERIFIED | `git status` clean before and after Phase 9 changes (only intended new/edited files present); no stray `__pycache__`, `.DS_Store`, or generated artifacts tracked. |

## README Finalization (9I.1)

`README.md` was refined, not rewritten: existing structure (16 sections)
and accurate prior-phase content were kept; the "Status" note under §4
and the technology-stack framing under §8, which still described the
project as of roughly Phase 4/5 ("quiz/MCQ/flashcard generation is not
implemented yet", "Nothing marked 'planned' is implemented yet"), were
updated to reflect that Phases 5–8 (study engine, application UI,
evaluation, security hardening) are now complete, and a new "Evaluation
Results", "Security", and "Limitations" section were added with the
Phase 7/8 headline figures and a link to `docs/final/*`.

## Final Test Execution (9I.2)

| Suite | Result |
|---|---|
| Backend tests (`uv run pytest -q`) | PASS — 505 passed, 4 deselected |
| Backend security tests (`uv run pytest tests/security -q`) | PASS — 70 passed |
| Backend lint (`uv run ruff check .`) | PASS — all checks passed |
| Backend type check (`uv run mypy app`) | PASS — no issues, 117 source files |
| Frontend tests (`pnpm test` / `vitest run`) | PASS — 13 passed, 6 files |
| Frontend lint (`pnpm run lint` / oxlint) | PASS — no errors |
| Frontend type check + build (`pnpm run build`) | PASS — `tsc -b && vite build` succeeded |
| oxlint | PASS (same as frontend lint — project uses oxlint, not ESLint) |
| Live backend E2E (manual, this session) | PASS for DOCX upload/list/BM25 search/delete/malformed-request/failure-path; BLOCKED for live PDF upload in this sandboxed shell (see `docs/final/PHASE_9_FINAL_REPORT.md` §11) |
| Ollama-dependent tests (HyDE, live generation, live study generation, VLM) | NOT AVAILABLE — Ollama not installed on PATH in this environment |
| Tesseract-dependent tests (live OCR) | NOT AVAILABLE — Tesseract not installed on PATH in this environment |
| faster-whisper live transcription | NOT ADDITIONALLY RUN — package importable, but no live audio file was transcribed in Phase 9 |

No blocked test was converted into a passing mock to hide the gap; every
BLOCKED/NOT AVAILABLE item above is also reflected in
`docs/final/FINAL_TEST_MATRIX.md`.

## Final Version Snapshot (9I.3)

See `docs/final/final_system_manifest.json`.
