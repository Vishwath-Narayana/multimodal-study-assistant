# Phase 8 Security Audit

Status: this document records the audit performed **before** Phase 8
implementation began (2026-09-04), against `develop` at commit
`5021da7` (Phase 0–7 merged, including Phase 7 evaluation/benchmarking).
It lists what was found, what was already in place from earlier phases,
and — for every finding — whether Phase 8 implements a mitigation.

See also: [THREAT_MODEL.md](THREAT_MODEL.md),
[SECURITY_TEST_MATRIX.md](SECURITY_TEST_MATRIX.md),
[SECURITY_CONFIGURATION.md](SECURITY_CONFIGURATION.md),
[PHASE_8_SECURITY_REPORT.md](PHASE_8_SECURITY_REPORT.md).

## Method

The audit read (not sampled) every file under `backend/app/` relevant to
upload handling, filesystem operations, document/image/audio parsing,
database access, API endpoints, prompt construction, and citation
validation, plus `backend/app/core/config.py`, `frontend/src/lib/api/*`,
and every `frontend/src` component that renders API-sourced content. It
also ran `pip-audit` (backend) and `pnpm audit` (frontend), and grepped the
repository for hard-coded secrets.

## Existing controls found (Phases 1–7, unchanged by Phase 8)

These were already implemented and are **not** duplicated by Phase 8:

- `app.ingestion.storage.sanitize_filename` + `DataPaths._resolve_within`:
  every on-disk path is resolved and checked against the data root; no
  user-controlled path can escape it (path traversal, absolute paths,
  `../`, null bytes, shell metacharacters all reduce to a safe bare
  filename with no separators).
- `app.ingestion.hashing`: document identity is `sha256(bytes)`, not the
  client-supplied filename — filename collisions cannot cause one
  document's file to overwrite another's.
- `app.ingestion.repository.DocumentRepository.delete`: explicit,
  transactional, dependency-ordered deletion of artifacts → study_items →
  chunks → document (schema.sql declares no `ON DELETE CASCADE`, so this
  is deliberate, not accidental).
- `app.multimodal.security`: image decompression-bomb guard
  (`Image.MAX_IMAGE_PIXELS` + file-size cap) and audio magic-byte sniffing,
  both already in place from Phase 4.
- `app.generation.prompts` / `app.study.prompts`: SYSTEM INSTRUCTIONS /
  RETRIEVED EVIDENCE / STUDENT QUESTION kept in three separated, labeled
  sections; the system instructions explicitly tell the model retrieved
  text is data, not instructions.
- `app.generation.citations.DeterministicCitationValidator`: every
  `[chunk:<id>]` citation is checked against the evidence actually
  retrieved for the current request — a model can never make a citation
  "true" merely by emitting it.
- All SQL access is parameterized (`sqlite3` placeholders); the one
  non-parameterized statement (`ALTER TABLE ... ADD COLUMN`) interpolates
  only developer-authored constants, never request input.
- No use of `eval`/`exec`/`pickle`/`yaml.load`/`os.system`/shell-invoked
  `subprocess` anywhere in the application code (`subprocess` is used only
  in `app/benchmarking/*`, dev-only tooling not reachable from any API
  endpoint, always with a literal argv list, never `shell=True`).
- No secrets, API keys, or credentials found in the repository (see
  "Dependency / Secret Audit" below).

## Findings

| # | Component | Finding | Severity | Phase 8 mitigation |
|---|-----------|---------|----------|---------------------|
| F1 | Ingestion upload | `validate_upload` checked extension and size only — no verification the file content actually matches the claimed type (spec 8B: "never trust ... file extension alone"). Audio uploads already had this via `app.multimodal.security._looks_like_audio`; documents did not. | Medium | **Implemented** — `app.ingestion.validation._looks_like_declared_type` checks PDF (`%PDF-`) and DOCX/PPTX (ZIP `PK\x03\x04`) magic bytes. HTML has no reliable binary signature and is documented as an accepted gap, matching the existing audio-validation precedent of "no known signature → don't false-reject." |
| F2 | Ingestion pipeline | No ceiling on parsed document size: page count, total extracted characters, or generated chunk count. A large-but-under-50MB document with pathological structure (e.g. thousands of tiny paragraphs) could produce an unbounded number of chunks, inflating embedding/indexing cost per request. | Medium | **Implemented** — `Settings.security_max_document_pages` / `security_max_extracted_chars` / `security_max_chunks_per_document`, enforced in `IngestionService._enforce_resource_limits` (pages/chars, checked right after parsing) and inline in `ingest()` (chunk count, checked right after chunking). |
| F3 | Multimodal ingestion | No ceiling on the number of images from *one document* sent through OCR/VLM. A document with many embedded images could trigger a correspondingly large number of OCR/VLM calls per upload. | Medium | **Implemented** — `Settings.security_max_artifacts_per_document`, enforced in `ImageEnrichmentService.enrich` (a per-instance counter; a fresh instance is built per ingest request). Images beyond the cap keep their original `image_path` (never dropped) but are not enriched. |
| F4 | Ingestion / audio ingestion | On a **failure after the raw file was already saved** (parser error, or — new in Phase 8 — a resource-limit rejection; and, for audio, any transcription failure), the raw uploaded bytes were left on disk indefinitely. Repeated uploads of different documents that always fail would accumulate disk usage without bound. | Medium | **Implemented** — both `IngestionService.ingest` and `AudioIngestionService._fail` now call `delete_document_files` on every failure path after the file was saved. |
| F5 | Prompt construction | `render_grounded_prompt`/`render_summary_prompt` (and every other `app.study.prompts` renderer) delimit sections with literal text markers (`=== STUDENT QUESTION ===`, `=== ANSWER ===`). A malicious document could embed one of these exact strings in its own content, attempting to forge a false section boundary inside the untrusted evidence block ("marker injection" / prompt-delimiter spoofing) — a stronger, more structural variant of ordinary prompt injection than the "ignore previous instructions" phrasing `docs/research/security.md` already tested for. | Medium | **Implemented** — `app.generation.prompt_security.neutralize_prompt_markers`, applied to every chunk's content before it is interpolated into either prompt renderer's evidence block. Breaks the literal marker shape while leaving the wording readable. Defense-in-depth, not a complete defense — see Limitations. |
| F6 | Prompt injection | No detection/logging layer existed for evidence containing injection-shaped text (spec 8D.3) — only the structural mitigation (evidence-is-data framing) existed, with no visibility into how often adversarial-looking content actually appears in retrieved evidence. | Low | **Implemented** — `app.generation.injection_detection`, a log-only heuristic scanner wired into `/chat/query` and every `/study/*` endpoint at the point evidence is retrieved. Never blocks or alters the request; only emits a `security.prompt_injection_signal` warning log. |
| F7 | Query validation | `ChatQueryRequest`/`SearchRequest`/`StudyScopeMixin`-derived schemas placed no upper bound on query string length or `top_k`, and the retrieval pipeline did not reject control characters in a query (which are logged verbatim in several places, e.g. `ingestion.completed ... filename=%s`, and could otherwise support log/terminal injection). | Medium | **Implemented** — `RetrievalService.retrieve` (the single choke point used by `/chat/query`, `/retrieval/search`, and every `/study/*` endpoint) now rejects queries over `Settings.security_max_query_length`, rejects a `top_k` outside `[1, Settings.security_max_top_k]`, and rejects queries containing disallowed Unicode control characters (`InvalidQueryError`). |
| F8 | API / error handling | A domain error (`RetrievalError`/`GenerationError`/`StudyError`) raised from inside a FastAPI `Depends()` provider (e.g. `get_bm25_retriever` building an index against an empty corpus) was **not** caught by the endpoint's own `try/except` — it propagated as a fully unhandled exception, which (without a registered handler) would surface a raw traceback in a non-debug ASGI deployment context in some configurations, and made the `TestClient` re-raise it directly in tests, meaning this code path had no test coverage at all. | Medium | **Implemented** — `app.main.create_app` registers `@app.exception_handler(RetrievalError/GenerationError/StudyError)`, each reusing that router's own `_ERROR_STATUS` mapping, so a dependency-raised domain error gets the same status code and safe message it would have gotten from inside the endpoint. A residual, lower-severity ordering quirk remains — see Limitations. |
| F9 | API / error handling | No handler existed for a *fully* unexpected exception (a bug, not a modeled domain error) — FastAPI/Starlette's own default behavior in some configurations can surface exception details. | Medium | **Implemented** — `app.main.create_app` registers a catch-all `@app.exception_handler(Exception)` that logs the full exception+traceback server-side (`logger.exception`) and always returns a generic `{"detail": "Internal server error."}` with no internal detail. |
| F10 | Server hardening | No response headers were set; `X-Content-Type-Options`/`X-Frame-Options`/`Referrer-Policy` were entirely absent, including on `GET /artifacts/{id}/file`, which serves user-uploaded-derived image bytes directly to a browser. | Low | **Implemented** — a middleware in `app.main.create_app` sets `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy: no-referrer` on every response. A full CSP was judged not applicable (see `SECURITY_CONFIGURATION.md`). |
| F11 | Dependency audit | `pip-audit` reports `transformers==5.8.1` (a transitive dependency of `sentence-transformers` and `docling-ibm-models`) is vulnerable to **CVE-2026-9856** (path traversal via crafted `chat_template` keys in `PreTrainedTokenizerBase.save_pretrained()`/`ProcessorMixin.save_pretrained()`), fixed in `5.10.0`. | Medium (exploitability: none in this application — see notes) | **Not upgraded** — `docling-ibm-models` pins `transformers<5.9.0` on macOS (`sys_platform == "darwin"`); `uv lock --upgrade-package transformers` confirmed the resolver cannot satisfy both constraints. This application never calls `save_pretrained()` on any tokenizer/processor anywhere in `app/` (grepped, zero occurrences), so the vulnerable code path is not reachable regardless of version. Documented as a residual/accepted risk pending an upstream `docling-ibm-models` release; see `PHASE_8_SECURITY_REPORT.md` "Dependency Audit". |
| F12 | Frontend | No findings. No `dangerouslySetInnerHTML`, no markdown-to-HTML rendering, no `eval`, no unsanitized URL construction found in `frontend/src`. All API-sourced content (answers, citations, filenames) is rendered as plain React text content, which auto-escapes. | Informational | No mitigation needed. |
| F13 | Frontend | No security-relevant secrets in `import.meta.env.VITE_*` — only `VITE_API_BASE_URL`, a non-sensitive local URL. | Informational | No mitigation needed. |
| F14 | Database | Delete cascade, foreign-key discipline, and parameterized queries already correct (see "Existing controls"); Phase 8 added dedicated regression tests (`tests/security/test_database_integrity.py`) that were previously only implicitly covered. | Informational | Tests added; no code change needed. |
| F15 | CORS / auth | `CORSMiddleware` reflects `Settings.cors_allowed_origins` (default `http://localhost:5173`) with `allow_methods=["*"]`/`allow_headers=["*"]` and no `allow_credentials` — acceptable for a local-first, single-user, cookie-free JSON API, but this is not a configuration safe to deploy multi-tenant or with a permissive origin list. No authentication/authorization exists anywhere in the application. | Informational (by design — see Non-Goals) | Documented, not changed — see "Explicit Non-Goals" in `docs/research/security.md` (unchanged from Phase 1) and Limitations below. |

## Duplicate/conflicting mechanisms

None found. `app.ingestion.validation.validate_upload` (documents) and
`app.multimodal.security.validate_audio_upload` (audio) intentionally
duplicate the extension/size-check *shape* (documented in both modules'
docstrings as a deliberate choice, not an oversight, since audio's
magic-byte check has no document equivalent) — Phase 8 preserved this
existing decision rather than forcing a shared abstraction across two
already-small, independently-tested functions.

## Dependency / Secret Audit

- **Frontend** (`pnpm audit`): 0 vulnerabilities across 217 dependencies.
- **Backend** (`pip-audit` against the resolved lockfile): 1 known
  vulnerability — see F11 above.
- **Secrets**: grepped for `api_key`, `secret`, `password`, `token=`,
  PEM/RSA private-key headers, and AWS-style key patterns across
  `backend/`, `frontend/src`, and `docs/`. No real credentials found. The
  only matches were: Pydantic config field names containing "token" that
  are unrelated to credentials (e.g. `generation_max_tokens`), a test
  fixture chunk id literally named `admin-secret-doc` (a fake identifier
  used to test citation rejection, not a real secret), and TypeScript
  standard-library type definitions in `node_modules` (not
  project code).
