"""SQLite persistence for documents and chunks.

Uses the standard-library ``sqlite3`` module directly rather than an ORM —
the schema is small (two tables) and Phase 0 deliberately avoided adding
dependencies not yet justified by a concrete requirement (see
docs/decisions/ADR-002-local-first.md). The schema itself lives in exactly
one place: schema.sql.
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from importlib import resources

from app.ingestion.models import BlockType, Chunk


def get_connection(database_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(database_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    schema_sql = resources.files("app.ingestion").joinpath("schema.sql").read_text()
    conn.executescript(schema_sql)
    conn.commit()


@dataclass
class StoredDocument:
    id: str
    filename: str
    file_type: str
    file_hash: str
    uploaded_at: str
    updated_at: str
    status: str
    page_count: int | None = None
    title: str | None = None
    author: str | None = None
    subject: str | None = None
    block_count: int | None = None
    chunk_count: int | None = None
    error_message: str | None = None


@dataclass
class DocumentUpsert:
    """Fields written on document creation/update. See DocumentRepository."""

    id: str
    filename: str
    file_type: str
    file_hash: str
    status: str
    page_count: int | None = None
    title: str | None = None
    author: str | None = None
    subject: str | None = None
    block_count: int | None = None
    chunk_count: int | None = None
    error_message: str | None = None


class DocumentRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def get_by_id(self, document_id: str) -> StoredDocument | None:
        row = self._conn.execute(
            "SELECT * FROM documents WHERE id = ?", (document_id,)
        ).fetchone()
        return _row_to_document(row) if row else None

    def get_by_hash(self, file_hash: str) -> StoredDocument | None:
        row = self._conn.execute(
            "SELECT * FROM documents WHERE file_hash = ?", (file_hash,)
        ).fetchone()
        return _row_to_document(row) if row else None

    def list_documents(self, limit: int = 50, offset: int = 0) -> list[StoredDocument]:
        rows = self._conn.execute(
            "SELECT * FROM documents ORDER BY uploaded_at DESC LIMIT ? OFFSET ?",
            (limit, offset),
        ).fetchall()
        return [_row_to_document(row) for row in rows]

    def upsert(self, values: DocumentUpsert) -> StoredDocument:
        existing = self.get_by_id(values.id)
        now = datetime.now(UTC).isoformat()
        uploaded_at = existing.uploaded_at if existing else now
        self._conn.execute(
            """
            INSERT INTO documents (
                id, filename, file_type, file_hash, uploaded_at, updated_at,
                status, page_count, title, author, subject, block_count,
                chunk_count, error_message
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                status = excluded.status,
                updated_at = excluded.updated_at,
                page_count = excluded.page_count,
                title = excluded.title,
                author = excluded.author,
                subject = excluded.subject,
                block_count = excluded.block_count,
                chunk_count = excluded.chunk_count,
                error_message = excluded.error_message
            """,
            (
                values.id,
                values.filename,
                values.file_type,
                values.file_hash,
                uploaded_at,
                now,
                values.status,
                values.page_count,
                values.title,
                values.author,
                values.subject,
                values.block_count,
                values.chunk_count,
                values.error_message,
            ),
        )
        self._conn.commit()
        result = self.get_by_id(values.id)
        assert result is not None
        return result


class ChunkRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def replace_for_document(self, document_id: str, chunks: Iterable[Chunk]) -> None:
        """Delete any existing chunks for this document and insert the given ones.

        Re-ingesting a document produces a fresh, deterministic chunk set
        (see docs/architecture/ingestion.md on chunk ID stability) rather
        than accumulating stale rows from a previous parse.
        """
        self._conn.execute("DELETE FROM chunks WHERE document_id = ?", (document_id,))
        self._conn.executemany(
            """
            INSERT INTO chunks (
                id, document_id, parent_id, order_index, chunk_type, content,
                page, section, heading_path, token_count, image_path,
                table_content, equation_content
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    chunk.id,
                    document_id,
                    chunk.parent_id,
                    chunk.order,
                    chunk.chunk_type.value,
                    chunk.content,
                    chunk.page,
                    chunk.section,
                    json.dumps(chunk.heading_path),
                    chunk.token_count,
                    chunk.image_path,
                    json.dumps(chunk.table_content) if chunk.table_content else None,
                    chunk.equation_content,
                )
                for chunk in chunks
            ],
        )
        self._conn.commit()

    def list_for_document(self, document_id: str) -> list[Chunk]:
        rows = self._conn.execute(
            "SELECT * FROM chunks WHERE document_id = ? ORDER BY order_index ASC",
            (document_id,),
        ).fetchall()
        return [_row_to_chunk(row) for row in rows]


def _row_to_document(row: sqlite3.Row) -> StoredDocument:
    return StoredDocument(**{key: row[key] for key in row.keys()})


def _row_to_chunk(row: sqlite3.Row) -> Chunk:
    return Chunk(
        id=row["id"],
        document_id=row["document_id"],
        parent_id=row["parent_id"],
        order=row["order_index"],
        chunk_type=BlockType(row["chunk_type"]),
        content=row["content"],
        page=row["page"],
        section=row["section"],
        heading_path=json.loads(row["heading_path"]) if row["heading_path"] else [],
        token_count=row["token_count"],
        image_path=row["image_path"],
        table_content=json.loads(row["table_content"]) if row["table_content"] else None,
        equation_content=row["equation_content"],
    )
