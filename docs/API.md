# API Design

Status: `GET /health` (Phase 0), the `/documents` endpoints (Phase 1), and
`POST /retrieval/search` (Phase 2) are implemented. Everything else below
is the planned API surface for later phases — documented ahead of
implementation so generation/explainability work has a stable contract to
build against, per [docs/roadmap.md](roadmap.md).

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
number.

**Response `400`** — empty query or invalid `mode`.
**Response `409`** — no chunks indexed yet.
**Response `503`** — HyDE requested but not configured/unreachable, or an
embedding/reranker model failed to load.

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
