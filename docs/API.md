# API Design

Status: `GET /health` (Phase 0), the `/documents` endpoints (Phase 1),
`POST /retrieval/search` (Phase 2), `POST /chat/query` (Phase 3),
`GET /documents/{id}/artifacts` + `GET /chunks/{id}` (Phase 4), the six
`POST /study/*` endpoints (Phase 5), and `DELETE /documents/{id}` +
`GET /artifacts/{id}/file` (Phase 6, added for the application UI) are
implemented. Everything under "Planned" below remains unimplemented.

## Implemented

### `GET /health`

Liveness check.

**Response `200`**
```json
{ "status": "ok" }
```

### `POST /documents/upload`

Uploads a document **or audio file** (multipart form field `file`) and
runs the full synchronous ingestion pipeline. For `pdf`/`docx`/`pptx`/
`html`/`htm`: validate → hash → parse → **Phase 4: OCR/VLM image
enrichment** → chunk → persist — see
[docs/architecture/ingestion.md](architecture/ingestion.md) and
[docs/architecture/multimodal.md](architecture/multimodal.md). For
`wav`/`mp3`/`m4a` (Phase 4): validate → hash → save → Whisper
transcription → timestamp-aware chunking → persist. One endpoint handles
every supported modality — the extension of the uploaded file selects
which pipeline runs.

**Implementation choice**: Phase 1 does not implement a separate
`POST /documents/ingest` trigger — upload and ingestion are one
synchronous call, since there is no background worker yet (see
docs/roadmap.md Phase 1 scope). A separate ingest-trigger endpoint may be
introduced if/when ingestion becomes asynchronous.

Supported types, size limits, and chunking parameters are configured via
`Settings` (`.env.example`), not hard-coded.

**Response `200`**
```json
{
  "document_id": "…sha256 hex…",
  "filename": "notes.pdf",
  "status": "completed",
  "page_count": 10,
  "block_count": 124,
  "chunk_count": 38,
  "duplicate": false,
  "error_message": null
}
```
`status` is one of `completed`, `duplicate`, or `failed` (`error_message`
set when `failed`). Re-uploading identical file content returns
`duplicate: true` with the previously computed counts rather than
re-parsing.

**Response `400`** — validation failure (unsupported extension, empty
file, oversized file): `{"detail": "<safe message>"}`.

### `GET /documents`

Lists ingested documents, most recently uploaded first.

**Response `200`**
```json
{ "documents": [ { "id": "...", "filename": "...", "status": "completed", "...": "..." } ] }
```

### `GET /documents/{document_id}`

Returns one document's stored metadata and status.

**Response `200`** — the same shape as one entry in `GET /documents`.
**Response `404`** — unknown document id.

### `DELETE /documents/{document_id}` (Phase 6)

Deletes a document and its dependent rows (`chunks`, `artifacts`,
`study_items`) plus its files under `data/raw` and `data/processed`.
Added for Phase 6's document library UI (spec section 5, "delete
document") — no such endpoint existed before. Foreign keys aren't declared
`ON DELETE CASCADE` (see `docs/architecture/database.md`), so dependents
are removed explicitly inside one transaction before the document row.
File cleanup is best-effort (a missing directory is not an error).

**Response `204`** — no body.
**Response `404`** — unknown document id.

### `GET /artifacts/{artifact_id}/file` (Phase 6)

Serves an artifact's original bytes (Phase 6's multimodal evidence UI needs
to display images/diagrams, which no endpoint exposed before). The stored
`storage_path` is resolved back to an absolute path through
`DataPaths.resolve_stored_path`, which rejects any path escaping the
configured data root — same discipline as every other file path on this
API.

**Response `200`** — the artifact's raw bytes, `Content-Type` set from the
stored `mime_type` (or `application/octet-stream` if unset).
**Response `404`** — unknown artifact id, or the file is missing on disk.

### `GET /documents/{document_id}/artifacts` (Phase 4)

Lists provenance records for a document's original image/audio artifacts
— see [docs/architecture/multimodal.md](architecture/multimodal.md)
"Provenance".

**Response `200`**
```json
{
  "artifacts": [
    {
      "id": "…", "document_id": "…", "chunk_id": "…",
      "artifact_type": "image", "storage_path": "processed/…/images/….png",
      "mime_type": "image/png", "sha256": "…",
      "metadata": {"page": 7, "vision_status": "available"},
      "created_at": "…"
    }
  ]
}
```
`storage_path` is relative to the data root — never an absolute filesystem
path. **Response `404`** — unknown document id.

### `GET /chunks/{chunk_id}` (Phase 4)

Returns one chunk's full stored representation, including every
multimodal field (`ocr_text`, `vlm_description`, `vision_status`,
`audio_start`/`audio_end`, `artifact_id`, `table_content`,
`equation_content`). A research/debug endpoint — unlike
`content_preview` elsewhere, this returns full `content`.

**Response `404`** — unknown chunk id.

### `POST /retrieval/search`

Research/debug endpoint for Phase 2 retrieval — **not** the final chat/
answer API (Phase 3+ adds that). See
[docs/architecture/retrieval.md](architecture/retrieval.md) for the full
pipeline design.

**Request**
```json
{ "query": "What is photosynthesis?", "mode": "hybrid_rrf", "top_k": 5 }
```
`mode` is one of `bm25`, `dense`, `dense_hyde`, `hybrid_rrf`,
`hybrid_rrf_hyde`, `full_baseline`.

**Response `200`**
```json
{
  "query": "What is photosynthesis?",
  "mode": "hybrid_rrf",
  "request_id": "…",
  "hyde_query": null,
  "results": [
    {
      "chunk_id": "…",
      "document_id": "…",
      "rank": 1,
      "score": 0.032,
      "retrieval_source": "rrf",
      "page": null,
      "section": "Section 1.1: Photosynthesis",
      "content_preview": "Photosynthesis converts light energy…",
      "bm25_rank": 1, "bm25_score": 1.9,
      "dense_rank": 2, "dense_score": 0.81,
      "rrf_score": 0.032, "rerank_score": null
    }
  ],
  "timing": { "bm25_ms": 0.4, "faiss_ms": 1.1, "rrf_ms": 0.02, "total_ms": 1.7, "...": null }
}
```
`content_preview` is truncated (never the full chunk text) and no file
path is ever exposed. `score`/`rank` are the *final* stage's values;
`bm25_*`/`dense_*`/`rrf_score`/`rerank_score` preserve each pipeline
stage's contribution when applicable — never collapsed into one ambiguous
number. As of Phase 4, each result also carries `chunk_type` (e.g.
`"image"`, `"table"`, `"transcript"`) when the underlying chunk's
metadata includes it — see
[docs/architecture/multimodal.md](architecture/multimodal.md).

**Response `400`** — empty query or invalid `mode`.
**Response `409`** — no chunks indexed yet.
**Response `503`** — HyDE requested but not configured/unreachable, or an
embedding/reranker model failed to load.

### `POST /chat/query`

Grounded generation + explainability (Phase 3) — see
[docs/architecture/generation.md](architecture/generation.md) for the full
pipeline. Not a chat/session API: no conversation memory, one query in, one
structured response out.

**Request**
```json
{ "query": "What is photosynthesis?", "retrieval_mode": "full_baseline", "top_k": 5 }
```
`retrieval_mode` accepts the same six values as `POST /retrieval/search`.

**Response `200`**
```json
{
  "request_id": "…",
  "query": "What is photosynthesis?",
  "answer": "Photosynthesis converts light energy into chemical energy [chunk:c1].",
  "answerable": true,
  "sufficiency": { "sufficient": true, "reason": "Evidence passed sufficiency checks." },
  "evidence": [
    {
      "chunk_id": "c1", "document_id": "…", "filename": "notes.pdf",
      "page": 4, "section": "Photosynthesis", "rank": 1,
      "retrieval_source": "reranker", "rerank_score": 4.1,
      "content_preview": "Photosynthesis converts light energy…",
      "attribution_score": 0.87, "attribution_rank": 1
    }
  ],
  "citations": [ { "chunk_id": "c1", "valid": true, "status": "valid", "document_id": "…", "filename": "notes.pdf", "page": 4, "section": "Photosynthesis" } ],
  "grounding": { "grounding_ratio": 0.83, "grounded_token_count": 10, "total_token_count": 12 },
  "claim_groundings": [ { "claim": "Photosynthesis converts light energy into chemical energy.", "supporting_chunk_ids": ["c1"], "grounding_ratio": 0.9 } ],
  "contradictions": { "has_conflict": false, "conflicts": [] },
  "timing": { "retrieval_ms": 12.0, "sufficiency_ms": 0.1, "generation_ms": 800.0, "citation_validation_ms": 0.05, "attribution_ms": 0.2, "grounding_ms": 0.3, "contradiction_ms": 0.1, "total_ms": 813.0 }
}
```
When `answerable` is `false` (evidence judged insufficient), `answer` is a
fixed abstention message, `citations`/`claim_groundings` are empty, and
`grounding` is `null` — the LLM is never called for an abstention.

As of Phase 4, `evidence` items and `citations` also carry `chunk_type`
plus any of `audio_start`/`audio_end`/`ocr_text`/`vlm_description`/
`original_artifact`/`table_content` the underlying chunk has, so a
citation identifies its modality — e.g. an audio citation reports
`"chunk_type": "transcript", "audio_start": 751.0, "audio_end": 788.0`
alongside its `[chunk:<id>]` marker. See
[docs/architecture/multimodal.md](architecture/multimodal.md)
"Generation + Citations".

**Response `400`** — empty query, or invalid `retrieval_mode` (same mapping
as `POST /retrieval/search`).
**Response `502`** — the LLM provider was reachable but generation failed.
**Response `503`** — the LLM provider is unreachable, or a Phase 2
dependency (HyDE, embedding/reranker model) failed to load.

### `POST /study/summary`, `/study/explain`, `/study/compare`, `/study/quiz`, `/study/mcq`, `/study/flashcards`

Study Engine (Phase 5) — see
[docs/architecture/study-engine.md](architecture/study-engine.md) for the
full pipeline. Six endpoints (not one unified `/study/generate`) because
each mode's request shape genuinely differs. Every mode reuses Phase 2
retrieval and Phase 3 sufficiency/citation/contradiction checking; none of
them implement their own retrieval or grounding.

All six accept `retrieval_mode` (same six values as `/retrieval/search`),
`top_k`, and an optional `document_id` to scope evidence to one
already-ingested document (`/study/compare` scopes both topics' retrieval
to the same document). `/study/quiz`, `/study/mcq`, `/study/flashcards`
additionally accept `count` (bounded by `study_min_count`/`study_max_count`)
and `difficulty` (`easy`/`medium`/`hard`); `/study/quiz` also accepts
`question_type` (`factual_recall`/`conceptual`/`application`/`comparison`);
`/study/summary` accepts `length` (`concise`/`standard`/`detailed`);
`/study/explain` accepts `style` (`simple`/`standard`/`detailed`).

**Request** (`/study/mcq`)
```json
{ "query": "CPU pipelining", "count": 5, "difficulty": "medium", "retrieval_mode": "full_baseline", "top_k": 8 }
```

**Response `200`** (`/study/mcq`)
```json
{
  "request_id": "…",
  "mode": "mcq",
  "query": "CPU pipelining",
  "answerable": true,
  "reason": null,
  "items": [
    {
      "question": "What is pipeline hazard?",
      "options": [
        { "id": "A", "text": "…" }, { "id": "B", "text": "…" },
        { "id": "C", "text": "…" }, { "id": "D", "text": "…" }
      ],
      "correct_option": "B",
      "explanation": "…",
      "difficulty": "medium",
      "citations": [ { "chunk_id": "c1", "valid": true, "status": "valid", "document_id": "…", "filename": "notes.pdf" } ],
      "source_chunk_ids": ["c1"]
    }
  ],
  "evidence": [ { "chunk_id": "c1", "document_id": "…", "filename": "notes.pdf", "rank": 1, "retrieval_source": "reranker", "content_preview": "…" } ],
  "sufficiency": { "sufficient": true, "reason": "Evidence passed sufficiency checks." },
  "contradictions": { "has_conflict": false, "conflicts": [] },
  "trace": {
    "provider": "ollama", "model": "deepseek-r1:8b",
    "stats": { "requested_count": 5, "generated_count": 5, "validated_count": 4, "rejected_count": 1, "duplicate_count": 0 },
    "timing": { "retrieval_ms": 12.0, "sufficiency_ms": 0.1, "generation_ms": 900.0, "parsing_ms": 0.2, "validation_ms": 0.3, "total_ms": 913.0 }
  }
}
```
`/study/summary`, `/study/explain`, `/study/compare` return a single
`item` object (`null` when `answerable` is `false`) instead of an `items`
array — a summary/explanation/comparison is one item, not a list.

When `answerable` is `false` (insufficient evidence for every mode, or —
for quiz/mcq/flashcards only — every generated item failed validation),
`items`/`item` is empty/`null` and `reason` explains why. The LLM is never
called for a sufficiency-driven abstention (same discipline as
`/chat/query`); for quiz/mcq/flashcards, the LLM *is* called but its output
is discarded if nothing survives validation — never silently substituted
with fabricated content.

**Response `400`** — empty query/topic, invalid `retrieval_mode`, invalid
`length`/`style`/`difficulty`/`question_type` enum value, or `count`
outside `[study_min_count, study_max_count]`.
**Response `502`** — the LLM provider was reachable but generation failed,
or its output could not be parsed into the requested structured shape
(quiz/mcq/flashcards/compare).
**Response `503`** — the LLM provider is unreachable, or a Phase 2
dependency failed to load.

## Planned

### Chat

- `GET /chat/{session_id}` — retrieve a session's message history (requires conversation memory, not yet implemented).

### Explainability

- `GET /evidence/{answer_id}` — retrieve a *persisted* answer's evidence/citations/scores by id (Phase 3's `/chat/query` already returns all of this inline per-request; this endpoint would require persisting past answers, which Phase 3 does not do).

## Conventions

- All request/response bodies are JSON; request models live in `app/schemas/`.
- Errors follow FastAPI's default `{"detail": ...}` shape unless a richer
  error contract is justified.
- No endpoint returns a generated answer without either citations or an
  explicit abstention reason — this is a design invariant, not an
  implementation detail to be added later.
