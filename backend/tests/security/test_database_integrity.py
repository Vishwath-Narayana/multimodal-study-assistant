"""Phase 8N: database integrity security tests (spec section 8I).

`DocumentRepository.delete()` already has a happy-path regression test
(`tests/ingestion/test_api_documents.py::test_delete_document_removes_it_and_its_chunks`).
This module adds the orphan-prevention and invalid-reference cases spec
section 8I specifically calls out: deleting one document must never affect
another, and every dependent table (chunks, artifacts, study_items) must be
fully cleaned up, not just the row count that happens to be asserted
elsewhere.
"""

from __future__ import annotations

import sqlite3

from app.ingestion.chunking import ChunkingConfig, chunk_document
from app.ingestion.models import BlockType, Chunk, DocumentBlock
from app.ingestion.repository import ChunkRepository, DocumentRepository, DocumentUpsert
from app.multimodal.models import Artifact, ArtifactType
from app.multimodal.repository import ArtifactRepository


def _upsert(conn: sqlite3.Connection, document_id: str) -> None:
    DocumentRepository(conn).upsert(
        DocumentUpsert(
            id=document_id,
            filename=f"{document_id}.pdf",
            file_type="pdf",
            file_hash=document_id,
            status="completed",
        )
    )


def _make_chunk(document_id: str, index: int) -> Chunk:
    return Chunk(
        id=f"{document_id}::chunk::{index:05d}",
        document_id=document_id,
        order=index,
        chunk_type=BlockType.PARAGRAPH,
        content=f"content {index}",
        token_count=2,
    )


def test_deleting_one_document_never_touches_another_documents_chunks(
    db_conn: sqlite3.Connection,
) -> None:
    _upsert(db_conn, "doc-a")
    _upsert(db_conn, "doc-b")
    chunk_repo = ChunkRepository(db_conn)
    chunk_repo.replace_for_document("doc-a", [_make_chunk("doc-a", 0), _make_chunk("doc-a", 1)])
    chunk_repo.replace_for_document("doc-b", [_make_chunk("doc-b", 0)])

    deleted = DocumentRepository(db_conn).delete("doc-a")
    assert deleted is True

    assert chunk_repo.get_by_id("doc-b::chunk::00000") is not None
    assert DocumentRepository(db_conn).get_by_id("doc-b") is not None
    assert chunk_repo.get_by_id("doc-a::chunk::00000") is None
    assert chunk_repo.get_by_id("doc-a::chunk::00001") is None
    assert DocumentRepository(db_conn).get_by_id("doc-a") is None


def test_deleting_a_document_removes_its_artifacts_but_not_anothers(
    db_conn: sqlite3.Connection,
) -> None:
    _upsert(db_conn, "doc-a")
    _upsert(db_conn, "doc-b")
    artifacts = ArtifactRepository(db_conn)
    artifacts.create(
        Artifact(
            id="doc-a::artifact::0",
            document_id="doc-a",
            artifact_type=ArtifactType.IMAGE,
            storage_path="processed/doc-a/images/0.png",
        )
    )
    artifacts.create(
        Artifact(
            id="doc-b::artifact::0",
            document_id="doc-b",
            artifact_type=ArtifactType.IMAGE,
            storage_path="processed/doc-b/images/0.png",
        )
    )

    DocumentRepository(db_conn).delete("doc-a")

    assert artifacts.get_by_id("doc-a::artifact::0") is None
    assert artifacts.get_by_id("doc-b::artifact::0") is not None


def test_deleting_a_document_removes_its_study_items_but_not_anothers(
    db_conn: sqlite3.Connection,
) -> None:
    _upsert(db_conn, "doc-a")
    _upsert(db_conn, "doc-b")
    db_conn.execute(
        "INSERT INTO study_items "
        "(id, request_id, mode, document_id, content, source_chunk_ids, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, datetime('now'))",
        ("item-a", "req-1", "summary", "doc-a", "{}", "[]"),
    )
    db_conn.execute(
        "INSERT INTO study_items "
        "(id, request_id, mode, document_id, content, source_chunk_ids, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, datetime('now'))",
        ("item-b", "req-2", "summary", "doc-b", "{}", "[]"),
    )
    db_conn.commit()

    DocumentRepository(db_conn).delete("doc-a")

    remaining = db_conn.execute("SELECT id FROM study_items").fetchall()
    remaining_ids = {row["id"] for row in remaining}
    assert remaining_ids == {"item-b"}


def test_deleting_unknown_document_returns_false_and_changes_nothing(
    db_conn: sqlite3.Connection,
) -> None:
    _upsert(db_conn, "doc-a")
    assert DocumentRepository(db_conn).delete("does-not-exist") is False
    assert DocumentRepository(db_conn).get_by_id("doc-a") is not None


def test_chunking_never_produces_duplicate_chunk_ids_for_one_document() -> None:
    """Orphan/inconsistency guard at the source: two structurally different
    blocks must never collide on the same generated chunk id within one
    document (which would make later deletes/lookups ambiguous)."""
    blocks = [
        DocumentBlock(
            id=f"doc1::block::{i:05d}", type=BlockType.PARAGRAPH, content=f"p{i}", order=i
        )
        for i in range(20)
    ]
    chunks = chunk_document("doc1", blocks, ChunkingConfig(target_tokens=5, overlap_tokens=1))
    ids = [c.id for c in chunks]
    assert len(ids) == len(set(ids))
