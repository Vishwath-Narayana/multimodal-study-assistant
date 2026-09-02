# API Design

Status: `GET /health` (Phase 0) and the `/documents` endpoints below
(Phase 1) are implemented. Everything else below is the planned API
surface for later phases — documented ahead of implementation so
retrieval/generation work has a stable contract to build against, per
[docs/roadmap.md](roadmap.md).

## Implemented

### `GET /health`

Liveness check.

**Response `200`**
```json
{ "status": "ok" }
```

### `POST /documents/upload`

Uploads a document (multipart form field `file`) and runs the full
synchronous ingestion pipeline (validate → hash → parse → chunk →
persist) — see [docs/architecture/ingestion.md](architecture/ingestion.md).
**Implementation choice**: Phase 1 does not implement a separate
`POST /documents/ingest` trigger — upload and ingestion are one
synchronous call, since there is no background worker yet (see
docs/roadmap.md Phase 1 scope). A separate ingest-trigger endpoint may be
introduced if/when ingestion becomes asynchronous.

Supported types, size limit, and chunking parameters are configured via
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

## Planned

### Documents

- `DELETE /documents/{id}` — remove a document and its derived chunks/embeddings.

### Chat

- `POST /chat/query` — ask a question; returns a grounded answer with citations, or an abstention.
- `GET /chat/{session_id}` — retrieve a session's message history.

### Explainability

- `GET /evidence/{answer_id}` — retrieve the evidence chunks, rerank scores, and attribution scores behind a given answer.

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
