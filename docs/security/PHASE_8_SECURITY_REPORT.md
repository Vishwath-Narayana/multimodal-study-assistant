# Phase 8 Security Report — Hardening & Security

Date: 2026-09-04
Branch: `feature/security-hardening` (based on `develop` @ `5021da7`, which
includes Phase 0–7 merged, including Phase 7 evaluation/benchmarking)

## 1. Objective

Harden the existing AI-Powered Multimodal Study Assistant (Phases 0–7,
treated as stable architecture) against the attack classes enumerated in
the Phase 8 brief: malicious uploads, path traversal, unsafe filenames,
malicious document content, prompt injection (direct and indirect),
document poisoning, malicious retrieved context, citation/evidence
manipulation, oversized inputs, resource exhaustion, malformed
audio/structured data, API abuse, unsafe error exposure, database
integrity issues, insecure temporary files, unbounded resource
consumption, and frontend/API trust-boundary problems — without rewriting
the stable Phase 0–7 architecture.

## 2. Security scope

In scope: `backend/app/**`, `frontend/src/**`, configuration
(`app.core.config.Settings`), the SQLite schema, and dependencies
(`backend/uv.lock`, `frontend/pnpm-lock.yaml`). Out of scope (per the
brief): introducing authentication, Kubernetes/Redis/Postgres/a
distributed queue, or any other architectural expansion beyond what a
specific finding required.

## 3. Existing security controls (Phases 1–7, verified, not duplicated)

- Filename sanitization + data-root path escape prevention
  (`app.ingestion.storage`).
- Content-hash document identity (`app.ingestion.hashing`) — filename
  collisions cannot overwrite unrelated documents.
- Explicit, transactional, dependency-ordered cascade delete
  (`DocumentRepository.delete`).
- Image decompression-bomb guard and audio magic-byte validation
  (`app.multimodal.security`, Phase 4).
- Evidence-is-data prompt framing with three separated, labeled sections
  (`app.generation.prompts`, `app.study.prompts`, Phase 3).
- Backend-controlled, per-request citation validation
  (`DeterministicCitationValidator`, Phase 3).
- 100% parameterized SQL; no `eval`/`exec`/`pickle`/`yaml.load`/
  `os.system`/shell-invoked `subprocess` anywhere in application code.

Full detail: `docs/security/SECURITY_AUDIT.md`.

## 4. Threat model

See `docs/security/THREAT_MODEL.md` — assets, five threat-actor
categories, and an attack-surface-by-attack-surface analysis (upload,
parsing, OCR/VLM/transcription, retrieval/generation, citations, API,
database, filesystem, frontend), each with impact/likelihood/mitigation/
residual risk.

## 5. Upload security

Extension validation, size limits, and filename sanitization already
existed (Phase 1). Phase 8 added: **magic-byte content validation** for
PDF/DOCX/PPTX (`app.ingestion.validation._looks_like_declared_type`) —
audio uploads already had this from Phase 4. HTML has no reliable binary
signature and is documented as an accepted gap. A single-file-per-request
upload endpoint (`POST /documents/upload`) structurally limits "maximum
files per request" to one; no change was needed there.

## 6. Parsing security

No execution path exists for embedded document content (PDF JavaScript,
DOCX/PPTX macros) — verified by code inspection, not just assumed. Phase 8
added resource ceilings enforced *after* parsing (page count, extracted
character count, generated chunk count — Docling does not expose these
before parsing completes) — see section 13.

## 7. Prompt injection

- **Direct injection** (via the user's own query): the shared retrieval
  choke point (`RetrievalService.retrieve`) now rejects queries with
  disallowed control characters and enforces a maximum length.
- **Indirect injection** (via retrieved document text): the existing
  evidence-is-data framing (Phase 3) is unchanged and still the primary
  defense. Phase 8 adds a **structural** mitigation new to this project:
  `app.generation.prompt_security.neutralize_prompt_markers` breaks any
  literal occurrence of a reserved section-boundary marker
  (`=== STUDENT QUESTION ===`, etc.) inside chunk content before it enters
  a prompt, closing a "marker injection" / prompt-delimiter-spoofing gap
  that plain evidence-is-data framing does not address on its own.
- **Detection (log-only)**: `app.generation.injection_detection` scans
  retrieved evidence for a small set of multi-word injection-shaped
  phrases and logs a `security.prompt_injection_signal` warning — it never
  blocks, rejects, or alters a request, and is explicitly tuned to avoid
  flagging ordinary academic use of words like "ignore" or "system".

**This does not make prompt injection impossible.** No prompt-engineering
or detection layer can guarantee an LLM will never be influenced by
adversarial text in its context window — see section 20 (Limitations).

## 8. Document poisoning

No new detection mechanism was added for *factually false but well-formed*
content — distinguishing that from legitimate content is a factual-
accuracy problem, not a security-boundary one, and provenance integrity
(section 9) is the practical mitigation available: a poisoned answer is
still correctly traceable to its source chunk, so it is falsifiable by a
reader, never silently presented as verified fact from nowhere.

## 9. Provenance integrity

Unchanged from Phase 3/4: every citation carries backend-controlled
`document_id`/`chunk_id`/`page`/`section`/`chunk_type`, never a value
accepted from model output. Phase 8 added regression tests specifically
attacking this boundary (fake/stale/cross-request citations) — see
section 11.

## 10. Citation security

`DeterministicCitationValidator` (Phase 3, unchanged) was audited and
attacked directly with seven new tests (`tests/security/
test_citation_attacks.py`): a fabricated id, a real id from outside the
current request's evidence, a stale id from a prior request, and an id
absent from any evidence — all correctly rejected. See section 11 for
results.

## 11. API security

Audited every router (`documents`, `chunks`, `artifacts`, `retrieval`,
`chat`, `study`, `health`). Findings and fixes:

- Query length/`top_k`/control-character validation added at the shared
  retrieval choke point (`security_max_query_length`, `security_max_top_k`).
- A domain error (`RetrievalError`/`GenerationError`/`StudyError`) raised
  from inside a FastAPI dependency provider (not from an endpoint's own
  `try/except`) previously had no registered handler; three new global
  exception handlers now map these using each router's existing
  `_ERROR_STATUS` dict, so a dependency-raised error gets the same status
  code and safe message an endpoint-raised one would.
- A catch-all handler for any other unhandled exception now logs the full
  exception server-side and always returns a generic, safe
  `{"detail": "Internal server error."}` — never a stack trace or internal
  path.

## 12. Database security

Audited: 100% parameterized queries (one non-parameterized `ALTER TABLE`
interpolates only developer-authored constants, never request input);
explicit, transactional, dependency-ordered cascade delete. Added five
regression tests specifically for orphan prevention (deleting one document
must never touch another's chunks/artifacts/study_items) and invalid-
reference handling.

## 13. Resource limits

Centralized in `Settings` (see `docs/security/SECURITY_CONFIGURATION.md`):
`SECURITY_MAX_QUERY_LENGTH`, `SECURITY_MAX_TOP_K`,
`SECURITY_MAX_DOCUMENT_PAGES`, `SECURITY_MAX_EXTRACTED_CHARS`,
`SECURITY_MAX_CHUNKS_PER_DOCUMENT`, `SECURITY_MAX_ARTIFACTS_PER_DOCUMENT`.
Enforced at: the shared retrieval choke point (query/top_k),
`IngestionService` (pages/chars/chunks, after parsing), and
`ImageEnrichmentService` (artifact cap, per-document counter).

## 14. Temporary file security

Found and fixed: both document ingestion (`IngestionService.ingest`) and
audio ingestion (`AudioIngestionService._fail`) previously left a failed
upload's raw bytes on disk indefinitely. Both now call
`delete_document_files` on every failure path that runs after the file was
saved (parser failure, resource-limit rejection, transcription failure).
Five regression tests cover the successful case (file kept) and every
failure case (file removed).

## 15. Frontend security

Audited `frontend/src/**`: no `dangerouslySetInnerHTML`, no markdown-to-
HTML rendering, no `eval`, no unsanitized URL construction. All API-
sourced content (answers, citations, filenames, error messages) renders as
plain React text content, which auto-escapes. No changes were needed.

## 16. Dependency audit

- **Frontend** (`pnpm audit`): 0 vulnerabilities, 217 total dependencies.
- **Backend** (`pip-audit` against the resolved `uv.lock`): 1 known
  vulnerability — `transformers==5.8.1`, **CVE-2026-9856** (path traversal
  in `PreTrainedTokenizerBase`/`ProcessorMixin`'s `save_pretrained()` via a
  crafted `chat_template` dict), fixed in `5.10.0`. **Not upgraded**:
  `docling-ibm-models` pins `transformers<5.9.0` on macOS; `uv lock
  --upgrade-package transformers` confirmed no resolvable version
  satisfies both constraints. **Practical exploitability in this
  application: none** — `save_pretrained()` is never called anywhere in
  `app/` (verified by grep across the entire backend). Documented as an
  accepted residual risk pending an upstream `docling-ibm-models` release;
  re-check when that package raises its pin.

## 17. Security tests

70 new tests added under `backend/tests/security/`:

| File | Tests |
|---|---|
| `test_upload_attacks.py` | 18 |
| `test_prompt_injection.py` | 13 |
| `test_citation_attacks.py` | 8 |
| `test_resource_limits.py` | 8 |
| `test_api_attacks.py` | 13 |
| `test_database_integrity.py` | 5 |
| `test_temp_file_cleanup.py` | 5 |

Full attack → mitigation → test → result mapping:
`docs/security/SECURITY_TEST_MATRIX.md`. Every row is `PASS` or explicitly
marked `NOT TESTED`/`NOT APPLICABLE` with a stated reason — none are
fabricated.

## 18. Test results

Baseline (before Phase 8, `develop` @ `5021da7`): **433 passed, 4
deselected** (`uv run pytest -q`).

After Phase 8:

- Backend: **505 passed, 4 deselected** (`uv run pytest -q`) — 70 new
  security tests + 2 new/adjusted validation tests, zero regressions.
- Frontend: **13 passed** (`pnpm test`), unchanged (frontend code was not
  modified this phase; audited only).
- `pip-audit`: 1 known vulnerability (documented, see section 16).
- `pnpm audit`: 0 vulnerabilities.

## 19. Build

- Frontend build (`pnpm run build`, `tsc -b && vite build`): **passes**,
  unchanged output size class (~277KB JS, ~19KB CSS).

## 20. Lint / type checking

- `ruff check .` (backend): **all checks passed**.
- `mypy app` (backend): **no issues found, 117 source files** (was 115
  before Phase 8 — 2 new modules: `app.generation.prompt_security`,
  `app.generation.injection_detection`).
- `oxlint` (frontend): **no errors** (unchanged — no frontend code
  modified).
- TypeScript (`tsc -b`, part of `pnpm run build`): **passes**.

## 21. Remaining vulnerabilities / residual risks

- **Prompt injection cannot be guaranteed eliminated.** The mitigations in
  this phase (marker neutralization, evidence-is-data framing, citation
  validation, log-only detection) reduce risk and close a specific
  structural gap (marker injection) but cannot guarantee a real LLM will
  never be influenced by adversarial text in its context window.
- **Document poisoning cannot be perfectly detected.** Provenance
  integrity (correct, backend-controlled citations) is the practical
  mitigation; distinguishing true from false-but-well-formed content is
  out of scope for a citation/provenance system.
- **`transformers` CVE-2026-9856** remains present transitively (see
  section 16) — not exploitable via any code path in this application, but
  not upgraded due to an upstream dependency pin.
- **No authentication/authorization** exists anywhere in the application —
  unchanged since Phase 1, by design for this local-first, single-user
  scope (see `THREAT_MODEL.md` Non-Goals).
- **No multi-tenant isolation.** Any client that can reach the API can
  read every uploaded document.
- **Dependency-resolution-order quirk** (Low severity, documented in
  `SECURITY_AUDIT.md` F8): a request with both an invalid body *and* an
  empty corpus can surface the corpus error (409) rather than a body-
  validation error (422), because FastAPI resolves `Depends()` providers
  alongside body validation. Both outcomes are safe (no internal detail
  leaked, no unhandled exception) — this is a response-code precision
  issue, not a security boundary failure.
- **HTML parsing SSRF** was analyzed by code inspection (no outbound-HTTP
  code path found in the parsing pipeline) but not empirically fuzzed
  against a live network monitor — see `THREAT_MODEL.md`.

## 22. Limitations

This application remains, as stated in every prior phase's security
documentation, a **local-first, single-user** system. It has not been
hardened for, and is not recommended for, multi-tenant or public-network
deployment without adding authentication/authorization and revisiting the
CORS configuration documented in `SECURITY_CONFIGURATION.md`. Security
testing in this phase used deterministic unit/API tests against
locally-controlled inputs; it did not include live adversarial-model
testing (no real LLM behavior was evaluated for injection compliance),
fuzz testing, or a live-network SSRF probe.

## 23. Conclusion

Phase 8 audited the complete Phase 0–7 system, found and fixed 9 concrete
gaps (magic-byte validation, four new resource ceilings, temporary-file
cleanup on two failure paths, prompt-marker-injection neutralization, a
log-only injection-detection layer, three new global exception handlers,
and security response headers), documented one accepted residual
dependency vulnerability with a verified-unreachable exploit path, and
added 70 new deterministic security tests with zero regressions against
the existing 433-test baseline. The system is **hardened against the
tested attack classes documented in `SECURITY_TEST_MATRIX.md`** — it is
not, and cannot honestly be described as, "fully secure" or "immune to
prompt injection/document poisoning"; see section 21/22 for the specific,
named residual risks.
