-- Phase 1 ingestion schema, extended in Phase 4 for multimodal content.
-- See docs/architecture/database.md.
-- Extends the Phase 0 design doc with the columns ingestion actually needs
-- (status tracking, extracted metadata, and per-block chunk fields); kept
-- in this single file so the schema is defined in exactly one place.
--
-- Phase 4 adds new nullable columns to `chunks` (ocr_text, vlm_description,
-- vision_status, audio_start, audio_end, artifact_id) and a new `artifacts`
-- table for original-artifact provenance. Both are additive: existing
-- Phase 1/2/3 rows are unaffected (new columns default to NULL). For a
-- database created before Phase 4, `CREATE TABLE IF NOT EXISTS` alone does
-- not add columns to an existing table — see
-- `app.ingestion.repository.init_db`'s explicit `ALTER TABLE` migration,
-- which runs after this script and is a no-op on a fresh database.

CREATE TABLE IF NOT EXISTS documents (
    id TEXT PRIMARY KEY,
    filename TEXT NOT NULL,
    file_type TEXT NOT NULL,
    file_hash TEXT NOT NULL UNIQUE,
    uploaded_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    status TEXT NOT NULL,
    page_count INTEGER,
    title TEXT,
    author TEXT,
    subject TEXT,
    block_count INTEGER,
    chunk_count INTEGER,
    error_message TEXT
);

CREATE TABLE IF NOT EXISTS chunks (
    id TEXT PRIMARY KEY,
    document_id TEXT NOT NULL REFERENCES documents(id),
    parent_id TEXT,
    order_index INTEGER NOT NULL,
    chunk_type TEXT NOT NULL,
    content TEXT NOT NULL,
    page INTEGER,
    section TEXT,
    heading_path TEXT,
    token_count INTEGER NOT NULL,
    image_path TEXT,
    table_content TEXT,
    equation_content TEXT,
    -- Phase 4 additions — see module docstring above.
    ocr_text TEXT,
    ocr_status TEXT,
    vlm_description TEXT,
    vision_status TEXT,
    artifact_id TEXT,
    audio_start REAL,
    audio_end REAL
);

CREATE INDEX IF NOT EXISTS idx_chunks_document_id ON chunks(document_id);
CREATE INDEX IF NOT EXISTS idx_documents_file_hash ON documents(file_hash);

-- Phase 4: original multimodal artifact provenance (spec section 5/7/24).
-- One row per original image/audio artifact preserved on disk — never the
-- artifact bytes themselves (stored under data/processed or data/raw, see
-- app.ingestion.storage / app.multimodal). `chunk_id` is nullable and set
-- once chunking assigns the final chunk id (see
-- app.multimodal.image_processing / app.multimodal.audio_service), so an
-- artifact never has to wait on a not-yet-known chunk id to be persisted —
-- but it is always linked back before ingestion completes, so no artifact
-- is left orphaned.
CREATE TABLE IF NOT EXISTS artifacts (
    id TEXT PRIMARY KEY,
    document_id TEXT NOT NULL REFERENCES documents(id),
    chunk_id TEXT,
    artifact_type TEXT NOT NULL,
    storage_path TEXT NOT NULL,
    mime_type TEXT,
    sha256 TEXT,
    metadata TEXT,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_artifacts_document_id ON artifacts(document_id);
CREATE INDEX IF NOT EXISTS idx_artifacts_chunk_id ON artifacts(chunk_id);
