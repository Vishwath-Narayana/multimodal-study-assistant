# Database Design

Status: **design document**. No database or ORM models exist yet in code
(Phase 0 only ships the FastAPI skeleton). This describes the intended
schema for later ingestion/retrieval/generation phases.

## Principles

- SQLite for local-first development. No PostgreSQL unless a concrete
  requirement emerges (see [ADR-003](../decisions/ADR-003-bm25-faiss-baseline.md)
  for the related retrieval-stack reasoning).
- Deliberately denormalized where normalization would add joins without
  adding value at this scale.
- Every table that participates in explainability carries enough foreign
  keys to reconstruct "why did the system say this" after the fact.

## Logical Entities

### documents
Uploaded source files.

| Column | Type | Notes |
|---|---|---|
| id | PK | |
| filename | text | original filename |
| file_type | text | pdf / docx / pptx / html / image / audio |
| file_hash | text | for dedup + provenance |
| uploaded_at | timestamp | |
| page_count | int, nullable | |
| status | text | e.g. pending / parsed / failed |

### chunks
Structure-aware chunks produced by ingestion.

| Column | Type | Notes |
|---|---|---|
| id | PK | |
| document_id | FK → documents | |
| parent_id | FK → chunks, nullable | for hierarchical parent/child retrieval (extension) |
| page | int, nullable | |
| section | text, nullable | |
| chunk_type | text | text / table / image / equation |
| content | text | chunk text, or OCR+VLM description for image chunks |
| image_path | text, nullable | original image reference, kept even when a VLM description exists |
| audio_start | float, nullable | seconds, for transcript chunks |
| audio_end | float, nullable | |

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
