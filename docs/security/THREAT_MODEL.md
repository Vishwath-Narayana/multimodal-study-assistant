# Phase 8 Threat Model

Scope: the AI-Powered Multimodal Study Assistant as a **local-first,
single-user** application (no authentication, no multi-tenant isolation —
see "Explicit Non-Goals" in `docs/research/security.md`, unchanged since
Phase 1). This threat model assumes that deployment scope; deploying this
application multi-tenant or on an untrusted network without adding
authentication/authorization is out of scope and explicitly not
recommended (see Limitations, `PHASE_8_SECURITY_REPORT.md`).

## Assets

| Asset | Where |
|---|---|
| User-uploaded documents (PDF/DOCX/PPTX/HTML/audio) | `data/raw/<document_id>/` |
| Extracted artifacts (images) | `data/processed/<document_id>/images/` |
| Document/chunk/artifact/study-item metadata | SQLite (`data/app.db`) |
| Generated answers, citations, study items | Returned via API; some persisted (`study_items` table) |
| Application configuration | `backend/.env` / environment variables (`app.core.config.Settings`) |
| Model prompts (system instructions) | `app.generation.prompts.SYSTEM_INSTRUCTIONS`, `app.study.prompts` |
| Local model weights / embeddings | `.venv` site-packages cache, FAISS index files under `data/indexes/` |

No asset here is a secret credential — the application holds no API keys,
passwords, or tokens for any external service (Ollama/tesseract/faster-
whisper are all local, unauthenticated processes).

## Threat actors

1. **Malicious student/user** — the person operating the application
   directly; can upload arbitrary files and send arbitrary API requests.
   In a local-first single-user deployment this actor is also the
   application's own operator, which bounds the *impact* of most attacks
   (see Limitations) but not the value of hardening against mistakes or a
   compromised/malicious file they were given by someone else.
2. **Malicious document author** — someone who authored/distributed a
   document (PDF, slide deck, etc.) that the user then uploads, without
   the user being the attacker. This is the primary threat actor for
   prompt injection, document poisoning, and malformed-file attacks.
3. **Compromised or malformed document** — not adversarial by
   intent, but capable of the same damage as #2 (corrupted PDF, truncated
   ZIP for DOCX/PPTX, a decompression-bomb image) — handled identically by
   the same mitigations.
4. **Automated abusive client** — a script hitting the API repeatedly
   with oversized/malformed/pathological requests, whether testing the
   application or attempting resource exhaustion.
5. **Accidental misuse** — the user themselves triggering a bad state
   (uploading the wrong file, sending a malformed request from a script)
   — not adversarial, but must fail safely.

## Attack surfaces and analysis

### Upload (`POST /documents/upload`)

- **Attack**: path traversal / malicious filename → escape the data root.
  **Impact**: arbitrary file write outside `data/`. **Likelihood**: Low
  (requires bypassing `sanitize_filename`). **Mitigation**:
  `app.ingestion.storage.sanitize_filename` + `DataPaths._resolve_within`
  (Phase 1, unchanged). **Residual risk**: none identified beyond
  filesystem-level TOCTOU races, out of scope for a local single-process
  app.
- **Attack**: upload a file whose content does not match its claimed
  extension (e.g. an executable renamed `.pdf`). **Impact**: attempt to
  get the parser (Docling) to process unexpected content, or to have a
  served artifact interpreted as something other than what its extension
  claims. **Likelihood**: Medium. **Mitigation**: magic-byte check (Phase
  8, F1). **Residual risk**: HTML has no reliable signature and is not
  checked; a non-HTML file with an `.html` extension still reaches the
  Docling HTML backend, which is expected to fail safely (parser error),
  not execute anything.
- **Attack**: oversized file / decompression bomb / pathological page
  count → resource exhaustion. **Impact**: memory/CPU/disk exhaustion,
  denial of service for a single-process local app. **Likelihood**:
  Medium. **Mitigation**: `max_upload_size_mb` (Phase 1) +
  `security_max_document_pages`/`security_max_extracted_chars`/
  `security_max_chunks_per_document` (Phase 8, F2). **Residual risk**: the
  ceilings apply *after* Docling has already parsed the whole document —
  a document could still be expensive to parse before being rejected. A
  pre-parse streaming page-count check is not available through Docling's
  current integration and was judged out of scope for Phase 8 (would
  require a different parsing strategy, not a security-config change).

### Document parsing (PDF/DOCX/PPTX/HTML)

- **Attack**: embedded JavaScript/macros/executable content.
  **Impact**: none if never executed. **Likelihood**: N/A — this
  application never executes embedded document content of any kind
  (verified: Docling extracts structural content only; no macro/script
  runner exists in `app/ingestion` or `app/multimodal`). **Mitigation**:
  architectural (no execution path exists). **Residual risk**: none
  identified.
- **Attack**: HTML document with external resource references
  (`<img src="http://...">`, remote stylesheets). **Impact**: if resolved
  during parsing, could act as an SSRF/tracking vector or hang on an
  unreachable host. **Likelihood**: Low — Docling's HTML backend parses
  structure/text; this project's own code never issues an HTTP request
  during document parsing (all outbound HTTP in `app/` targets the local
  Ollama server, `app.retrieval.llm_client`/`app.multimodal.vision`, or is
  test-only). **Residual risk**: not independently verified against every
  Docling HTML-backend version's exact fetch behavior; documented as a
  limitation, not empirically fuzzed in Phase 8 (would require a
  monitored-network test harness beyond this phase's scope).

### OCR / VLM / transcription

- **Attack**: a decompression-bomb or oversized extracted image reaching
  OCR/VLM. **Mitigation**: `app.multimodal.security.validate_image_artifact`
  (Phase 4, unchanged). **Attack**: excessive image count per document.
  **Mitigation**: `security_max_artifacts_per_document` (Phase 8, F3).
  **Attack**: malformed audio file. **Mitigation**:
  `app.multimodal.security.validate_audio_upload` magic-byte check (Phase
  4, unchanged).

### Retrieval / generation (prompt injection, document poisoning)

- **Attack**: a document's text instructs the model to ignore its
  instructions, reveal its system prompt, or otherwise act outside its
  role. **Impact**: potentially misleading or non-grounded output;
  **cannot** result in credential/secret disclosure (none exist in the
  prompt) or in an invalid citation being accepted (see Citation Security
  below), but could still produce an unhelpful/wrong answer if a real
  model complies with the injected text. **Likelihood**: Medium (widely
  known attack pattern; any uploaded document could attempt this).
  **Mitigation**: evidence-is-data prompt framing (Phase 3) + marker
  neutralization (Phase 8, F5) + citation validation backstop (Phase 3,
  unchanged) + log-only detection (Phase 8, F6). **Residual risk**:
  **cannot be eliminated** — an LLM's behavior in the face of adversarial
  context is not something any prompt-engineering or detection layer can
  guarantee against; this is documented, not overclaimed (see
  `PHASE_8_SECURITY_REPORT.md` Limitations).
- **Attack**: document poisoning — repeated or "authoritative-sounding"
  false statements designed to be retrieved and treated as ground truth.
  **Impact**: a wrong-but-plausible answer, still correctly *cited* to
  the poisoned chunk (provenance is preserved, so the answer is
  falsifiable by checking the source — it is not silently fabricated).
  **Likelihood**: Medium. **Mitigation**: none beyond correct provenance
  and the sufficiency/contradiction checks already in place (Phase 3) —
  detecting *false but well-formed* content is a factual-accuracy problem,
  not a security-boundary problem, and is explicitly out of scope for a
  citation/provenance system (spec section 8E acknowledges "implement
  mitigations where practical" — provenance integrity is the practical
  mitigation available here). **Residual risk**: not eliminated, by
  design — see Limitations.

### Citations

- **Attack**: a compromised/manipulated model output claims a citation to
  a chunk_id it invented, or to a real chunk_id that was never part of
  this request's retrieved evidence (cross-request citation leakage).
  **Impact**: none if validation holds — an invalid citation is reported
  as such (`UNKNOWN_CHUNK`/`NOT_IN_RETRIEVED_EVIDENCE`), never silently
  accepted. **Likelihood**: Medium (directly encouraged by a successful
  prompt injection). **Mitigation**: `DeterministicCitationValidator`
  (Phase 3, unchanged) — attacked directly by
  `tests/security/test_citation_attacks.py` (Phase 8). **Residual risk**:
  none identified within the validator's own logic; a *user-facing* risk
  remains if a caller trusts an "invalid" citation's `chunk_id`/`document_id`
  string as if it were verified data — the response schema always carries
  a `status`/`valid` field precisely so a caller can distinguish this.

### API

- **Attack**: malformed JSON, wrong field types, invalid path parameters,
  unsupported HTTP methods. **Mitigation**: Pydantic schema validation
  (422) + FastAPI's default method/route dispatch (404/405), both
  pre-existing; **Attack**: a domain error raised from a dependency
  provider bypassing an endpoint's own error handling. **Mitigation**:
  Phase 8 global exception handlers (F8/F9). **Residual risk**: see
  `SECURITY_AUDIT.md` F8's note on dependency-resolution ordering vs.
  body validation (Low severity, documented, not fixed — would require
  restructuring FastAPI dependency wiring, judged out of proportion to the
  risk for a local-first single-user app).
- **Attack**: pathologically long query / out-of-range `top_k` / control
  characters in a query. **Mitigation**: Phase 8, F7.

### Database

- **Attack**: SQL injection. **Mitigation**: 100% parameterized queries
  (verified by audit, `SECURITY_AUDIT.md`). **Attack**: deleting a
  document orphans or leaks another document's rows. **Mitigation**:
  explicit dependency-ordered delete (Phase 1, unchanged), regression-
  tested in Phase 8 (`tests/security/test_database_integrity.py`).

### Filesystem / temporary files

- **Attack**: a failed upload leaves files accumulating on disk
  indefinitely (disk-exhaustion via repeated failed uploads).
  **Mitigation**: Phase 8, F4.

### Frontend

- **Attack**: XSS via a malicious filename, citation, or generated answer
  rendered in the UI. **Mitigation**: architectural — no
  `dangerouslySetInnerHTML`, no markdown-to-HTML rendering anywhere in
  `frontend/src` (verified by audit); all such content renders as escaped
  React text. **Residual risk**: none identified for the current frontend
  implementation; would need re-auditing if a markdown renderer is added
  in a future phase.

## Non-goals (unchanged from Phase 1, restated here for completeness)

- No authentication/authorization system.
- No multi-tenant isolation — any client that can reach the API can read
  every uploaded document and every generated answer.
- No network-facing deployment hardening beyond the CORS/security-header
  defaults documented in `SECURITY_CONFIGURATION.md` — this application is
  not intended for production multi-user deployment as-is.
- No sandboxing subsystem for document parsing (Docling/python-docx/
  python-pptx run in-process).
