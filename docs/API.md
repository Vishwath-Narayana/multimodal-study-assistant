# API Design

Status: `GET /health` (Phase 0), the `/documents` endpoints (Phase 1),
`POST /retrieval/search` (Phase 2), `POST /chat/query` (Phase 3), and
`GET /documents/{id}/artifacts` + `GET /chunks/{id}` (Phase 4) are
implemented. Everything else below is the planned API surface for later
phases — documented ahead of implementation so the study-engine work has
a stable contract to build against, per [docs/roadmap.md](roadmap.md).

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

## Planned

### Documents

- `DELETE /documents/{id}` — remove a document and its derived chunks/embeddings.

### Chat

- `GET /chat/{session_id}` — retrieve a session's message history (requires conversation memory, not yet implemented).

### Explainability

- `GET /evidence/{answer_id}` — retrieve a *persisted* answer's evidence/citations/scores by id (Phase 3's `/chat/query` already returns all of this inline per-request; this endpoint would require persisting past answers, which Phase 3 does not do).

### Study Engine

- `POST /study/summary`
- `POST /study/quiz`
- `POST /study/mcq`
- `POST /study/flashcards`
- `POST /study/compare`

Each accepts a document/chunk scope and returns generated study items with
`source_chunk_ids` for traceability (see [docs/architecture/database.md](architecture/database.md)).

## Conventions (for when these are implemented)

- All request/response bodies are JSON; request models live in `app/schemas/`.
- Errors follow FastAPI's default `{"detail": ...}` shape unless a richer
  error contract is justified.
- No endpoint returns a generated answer without either citations or an
  explicit abstention reason — this is a design invariant, not an
  implementation detail to be added later.
