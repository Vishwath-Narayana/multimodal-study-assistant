# API Design

Status: only `GET /health` is implemented (Phase 0). Everything else below
is the planned API surface for later phases — documented ahead of
implementation so ingestion/retrieval/generation work has a stable contract
to build against, per [docs/roadmap.md](roadmap.md).

## Implemented

### `GET /health`

Liveness check.

**Response `200`**
```json
{ "status": "ok" }
```

## Planned

### Documents

- `POST /documents/upload` — upload a raw file (PDF/DOCX/PPTX/HTML/image/audio).
- `POST /documents/ingest` — trigger parsing/chunking/embedding for an uploaded document.
- `GET /documents` — list uploaded documents and their status.
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
