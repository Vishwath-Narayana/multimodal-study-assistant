-- Phase 1 ingestion schema. See docs/architecture/database.md.
-- Extends the Phase 0 design doc with the columns ingestion actually needs
-- (status tracking, extracted metadata, and per-block chunk fields); kept
-- in this single file so the schema is defined in exactly one place.

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
    equation_content TEXT
);

CREATE INDEX IF NOT EXISTS idx_chunks_document_id ON chunks(document_id);
CREATE INDEX IF NOT EXISTS idx_documents_file_hash ON documents(file_hash);
