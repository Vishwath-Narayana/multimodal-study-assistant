# Database Design

Status: **`documents` and `chunks` are implemented** (Phase 1, extended in
Phase 4), and **`artifacts` is implemented** (Phase 4) — schema defined
once in `backend/app/ingestion/schema.sql`, loaded by
`app/ingestion/repository.py::init_db`. Everything below that (embeddings
onward) is still a design-only plan for later phases. The implemented
tables extend this Phase 0 design with the columns ingestion actually
needs (status tracking, extracted metadata, per-chunk structured-content
and multimodal fields) — differences from the original design are called
out inline.

## Principles

- SQLite for local-first development. No PostgreSQL unless a concrete
  requirement emerges (see [ADR-003](../decisions/ADR-003-bm25-faiss-baseline.md)
  for the related retrieval-stack reasoning).
- Deliberately denormalized where normalization would add joins without
  adding value at this scale.
- Every table that participates in explainability carries enough foreign
  keys to reconstruct "why did the system say this" after the fact.

## Logical Entities

### documents — implemented
Uploaded source files.

| Column | Type | Notes |
|---|---|---|
| id | TEXT PK | = the file's SHA-256 hash (see ingestion.md §3) |
| filename | TEXT | original filename |
| file_type | TEXT | pdf / docx / pptx / html / htm |
| file_hash | TEXT UNIQUE | SHA-256, for dedup + provenance |
| uploaded_at | TEXT (ISO 8601) | set once, preserved across re-ingestion |
| updated_at | TEXT (ISO 8601) | *(added in Phase 1)* bumped on every status change |
| status | TEXT | `processing` / `completed` / `failed` (see ingestion.md §10) |
| page_count | INTEGER, nullable | |
| title | TEXT, nullable | *(added in Phase 1)* extracted document title |
| author | TEXT, nullable | *(added in Phase 1)* |
| subject | TEXT, nullable | *(added in Phase 1)* |
| block_count | INTEGER, nullable | *(added in Phase 1)* |
| chunk_count | INTEGER, nullable | *(added in Phase 1)* |
| error_message | TEXT, nullable | *(added in Phase 1)* safe, user-facing failure reason |

### chunks — implemented
Structure-aware chunks produced by ingestion.

| Column | Type | Notes |
|---|---|---|
| id | TEXT PK | deterministic, see ingestion.md §6 |
| document_id | TEXT FK → documents | |
| parent_id | TEXT, nullable | references a synthetic per-section chunk's id (not a FK constraint, since parent rows share the same table); data representation only — not used for retrieval in Phase 1 |
| order_index | INTEGER | *(named `order_index`, not `order` — reserved word in SQL)* |
| chunk_type | TEXT | heading / paragraph / list / table / image / equation / code / caption / unknown |
| content | TEXT | chunk text, or a plain-text table rendering for table chunks |
| page | INTEGER, nullable | |
| section | TEXT, nullable | deepest heading title |
| heading_path | TEXT, nullable | *(added in Phase 1)* JSON array of ancestor heading titles |
| token_count | INTEGER | *(added in Phase 1)* whitespace-approximate token count |
| image_path | TEXT, nullable | path relative to `data/`, kept even before any VLM description exists |
| table_content | TEXT, nullable | *(added in Phase 1)* JSON `list[list[str]]` grid |
| equation_content | TEXT, nullable | raw equation text where Docling detects one (see ingestion.md §4 limitations) |
| ocr_text | TEXT, nullable | *(added in Phase 4)* OCR-extracted text from an image artifact |
| ocr_status | TEXT, nullable | *(added in Phase 4)* `VisionStatus`: not_attempted / available / unavailable / failed |
| vlm_description | TEXT, nullable | *(added in Phase 4)* VLM-generated image/diagram description |
| vision_status | TEXT, nullable | *(added in Phase 4)* same enum, for the VLM description |
| artifact_id | TEXT, nullable | *(added in Phase 4)* FK to `artifacts.id` |
| audio_start | REAL, nullable | *(added in Phase 4)* seconds, for `chunk_type = transcript` |
| audio_end | REAL, nullable | *(added in Phase 4)* seconds, for `chunk_type = transcript` |

The Phase 4 columns were added via an additive `ALTER TABLE` migration
(`app.ingestion.repository._migrate_phase4_columns`, run on every
`init_db()` call) rather than a schema rewrite, so an existing Phase 1-3
database keeps its `documents`/`chunks` data.

### artifacts — implemented (Phase 4)
Provenance for original image/audio artifacts (see
[docs/architecture/multimodal.md](multimodal.md) "Provenance").

| Column | Type | Notes |
|---|---|---|
| id | TEXT PK | deterministic (`<document_id>::artifact::<block_id>` for images, `<document_id>::artifact::audio` for audio) |
| document_id | TEXT FK → documents | |
| chunk_id | TEXT, nullable | backfilled once chunking assigns the final chunk id (images); stays `NULL` for audio (one artifact, many chunks — see multimodal.md) |
| artifact_type | TEXT | `image` / `audio` |
| storage_path | TEXT | relative to `data/`, never absolute |
| mime_type | TEXT, nullable | |
| sha256 | TEXT, nullable | |
| metadata | TEXT, nullable | JSON, e.g. `{"page": 7, "vision_status": "available"}` |
| created_at | TEXT (ISO 8601) | |

### embeddings
Vector index pointers, decoupled from the FAISS index itself.

| Column | Type | Notes |
|---|---|---|
| chunk_id | FK → chunks | |
| vector_id | int | position in the FAISS index |
| model_name | text | e.g. `BAAI/bge-small-en-v1.5`, for reproducibility when models change |

### sessions
A chat session.

| Column | Type | Notes |
|---|---|---|
| id | PK | |
| created_at | timestamp | |

### messages
Turns within a session.

| Column | Type | Notes |
|---|---|---|
| id | PK | |
| session_id | FK → sessions | |
| role | text | user / assistant |
| content | text | |
| timestamp | timestamp | |

### answers
Generated answers with their explainability scores.

| Column | Type | Notes |
|---|---|---|
| id | PK | |
| message_id | FK → messages | |
| answer | text | |
| grounding_ratio | float, nullable | |
| citation_validity | float, nullable | |
| confidence | float, nullable | |

### evidence
The evidence chunks behind an answer.

| Column | Type | Notes |
|---|---|---|
| answer_id | FK → answers | |
| chunk_id | FK → chunks | |
| rank | int | position after fusion/reranking |
| rerank_score | float | |
| attribution_score | float, nullable | |

### study_items
Generated study material (quiz / MCQ / flashcard / summary).

| Column | Type | Notes |
|---|---|---|
| id | PK | |
| type | text | quiz / mcq / flashcard / summary / comparison |
| question | text, nullable | |
| answer | text | |
| source_chunk_ids | text (JSON array) | traceability back to evidence |

## Non-Goals

- No multi-tenant user model in Phase 0–N; this is a single-user local tool
  until a concrete multi-user requirement exists.
- No migration framework decision yet — will be revisited when the schema
  above is actually implemented (Phase 1+).
