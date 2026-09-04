# Security Configuration

All security/resource limits are centralized in `app.core.config.Settings`
(`backend/app/core/config.py`) — none are hard-coded elsewhere in the
application. This document lists every security-relevant setting: its
default, valid range, and rationale. Every value below is an
implementation choice for this local-first, single-user project, not a
value mandated by EduRAG or any external standard.

## Phase 8 additions

| Setting | Default | Rationale |
|---|---|---|
| `SECURITY_MAX_QUERY_LENGTH` | `4000` (chars) | Generous for any legitimate student question (a full paragraph is well under this) while bounding embedding/tokenization cost per request. Enforced in `RetrievalService.retrieve`, the single choke point shared by `/chat/query`, `/retrieval/search`, and every `/study/*` endpoint. |
| `SECURITY_MAX_TOP_K` | `100` | Far above `FINAL_TOP_K` (5, the production default) but still bounded — prevents a caller from forcing reranking/attribution over an unbounded candidate pool. |
| `SECURITY_MAX_DOCUMENT_PAGES` | `1000` | A four-figure page count covers essentially any real course document (textbooks included) while bounding worst-case indexing cost for a pathological upload. Enforced after parsing (Docling does not expose page count before parsing completes). |
| `SECURITY_MAX_EXTRACTED_CHARS` | `10,000,000` (10M characters) | Roughly 2000 pages of dense text — well above any real document, bounding total in-memory/indexed text size for a document that parses into many small blocks. |
| `SECURITY_MAX_CHUNKS_PER_DOCUMENT` | `10,000` | At `~512` tokens/chunk (`CHUNK_TARGET_TOKENS`) this covers a multi-thousand-page document; bounds worst-case embedding/indexing calls from one upload. |
| `SECURITY_MAX_ARTIFACTS_PER_DOCUMENT` | `200` | Bounds worst-case OCR/VLM calls triggered by one document. Images beyond this count keep their original `image_path` (never dropped, spec section 7) but are not enriched. |

## Pre-existing settings (Phases 1–4, unchanged)

| Setting | Default | Rationale |
|---|---|---|
| `MAX_UPLOAD_SIZE_MB` | `50` | Local-first sanity limit for a course document. |
| `MAX_AUDIO_UPLOAD_SIZE_MB` | `200` | Audio files are inherently larger than text documents. |
| `MAX_IMAGE_ARTIFACT_SIZE_MB` | `20` | Applied to one already-extracted image, not the whole source document. |
| `MAX_IMAGE_PIXELS` | `40,000,000` | Pillow decompression-bomb guard (`Image.MAX_IMAGE_PIXELS`). |
| `SUPPORTED_EXTENSIONS_RAW` | `pdf,docx,pptx,html,htm` | The formats this project's ingestion pipeline (Docling) actually supports. |
| `AUDIO_SUPPORTED_EXTENSIONS_RAW` | `wav,mp3,m4a` | The formats `app.multimodal.transcription` supports. |
| `GENERATION_TIMEOUT_SECONDS` / `HYDE_TIMEOUT_SECONDS` / `VLM_TIMEOUT_SECONDS` / `STUDY_TIMEOUT_SECONDS` | `120` / `30` / `60` / `120` | Bound how long one request can block on a local Ollama call. |
| `STUDY_MIN_COUNT` / `STUDY_MAX_COUNT` | `1` / `20` | Spec section 31: a requested item count outside this range is rejected explicitly, not clamped silently. |

## Minimum / maximum guidance for operators

- `SECURITY_MAX_QUERY_LENGTH`: do not set below ~500 (would reject
  reasonable multi-sentence questions) or above ~20000 (defeats the point
  of the limit; a single request could still be expensive).
- `SECURITY_MAX_TOP_K`: do not set below `FINAL_TOP_K`'s configured value
  (the response would always look truncated) or in the tens of thousands
  (defeats the limit's purpose).
- `SECURITY_MAX_DOCUMENT_PAGES` / `SECURITY_MAX_EXTRACTED_CHARS` /
  `SECURITY_MAX_CHUNKS_PER_DOCUMENT`: raise together if the deployment's
  real course material regularly exceeds these (e.g. a bound multi-volume
  textbook); lowering them independently of real document sizes will start
  rejecting legitimate uploads.
- `SECURITY_MAX_ARTIFACTS_PER_DOCUMENT`: raise if OCR/VLM providers are
  fast/cheap in a given deployment (e.g. a small local model); the default
  assumes each OCR/VLM call has non-trivial latency.

## Server hardening (spec section 8S)

- **Security headers**: `X-Content-Type-Options: nosniff`,
  `X-Frame-Options: DENY`, `Referrer-Policy: no-referrer` are applied to
  every response (`app.main.create_app`'s security-headers middleware).
- **Content-Security-Policy**: **not applicable** — this is a JSON API
  with no server-rendered HTML page of its own (the frontend is a
  separately-served Vite/React SPA); a CSP header on JSON responses has no
  effect. If a future phase adds server-rendered HTML, a CSP should be
  added at that point.
- **CORS**: `CORSMiddleware` reflects `CORS_ALLOWED_ORIGINS` (default
  `http://localhost:5173`, the Vite dev server) with `allow_methods=["*"]`
  /`allow_headers=["*"]` and no `allow_credentials`. This is an
  appropriate **development** default for a local-first single-user app —
  it is **not** a hardened multi-tenant/production CORS configuration.
  An operator deploying this beyond local development must set
  `CORS_ALLOWED_ORIGINS` to the actual frontend origin(s) and should not
  set it to `*` if `allow_credentials` is ever enabled in the future.
- **Authentication**: none. See `docs/research/security.md` "Explicit
  Non-Goals" (unchanged since Phase 1) and `THREAT_MODEL.md`.

## Required environment variables

None of the settings above are required — every one has a safe default.
The only environment variables that change *behavior* rather than tuning
a limit are the optional provider toggles (`VLM_PROVIDER`, `OCR_PROVIDER`,
`TRANSCRIPTION_PROVIDER`), which default to disabled/empty so the default
test suite and a fresh checkout never require an external model to be
running.
