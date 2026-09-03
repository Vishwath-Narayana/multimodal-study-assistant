"""Artifact provenance persistence + the Phase 4 chunks-table migration."""

from __future__ import annotations

import sqlite3

from app.ingestion.models import BlockType, Chunk, VisionStatus
from app.ingestion.repository import ChunkRepository, DocumentRepository, DocumentUpsert, init_db
from app.multimodal.models import Artifact, ArtifactType
from app.multimodal.repository import ArtifactRepository


def _make_document(conn: sqlite3.Connection, document_id: str = "doc1") -> None:
    DocumentRepository(conn).upsert(
        DocumentUpsert(
            id=document_id,
            filename="f.pdf",
            file_type="pdf",
            file_hash=document_id,
            status="completed",
        )
    )


def test_init_db_migration_is_idempotent(db_conn: sqlite3.Connection) -> None:
    # init_db already ran once via the db_conn fixture; running it again
    # must not raise "duplicate column" or otherwise fail.
    init_db(db_conn)
    columns = {row["name"] for row in db_conn.execute("PRAGMA table_info(chunks)").fetchall()}
    expected = {
        "ocr_text",
        "vlm_description",
        "vision_status",
        "audio_start",
        "audio_end",
        "artifact_id",
    }
    assert expected <= columns


def test_artifacts_table_exists(db_conn: sqlite3.Connection) -> None:
    rows = db_conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    tables = {row["name"] for row in rows}
    assert "artifacts" in tables


def test_artifact_create_and_get_by_id(db_conn: sqlite3.Connection) -> None:
    _make_document(db_conn)
    repo = ArtifactRepository(db_conn)
    artifact = repo.create(
        Artifact(
            id="art1",
            document_id="doc1",
            artifact_type=ArtifactType.IMAGE,
            storage_path="processed/doc1/images/block1.png",
            mime_type="image/png",
            sha256="deadbeef",
            metadata={"page": 3},
        )
    )
    assert artifact.chunk_id is None
    fetched = repo.get_by_id("art1")
    assert fetched is not None
    assert fetched.storage_path == "processed/doc1/images/block1.png"
    assert fetched.metadata == {"page": 3}


def test_artifact_set_chunk_id_backfills(db_conn: sqlite3.Connection) -> None:
    _make_document(db_conn)
    repo = ArtifactRepository(db_conn)
    repo.create(
        Artifact(
            id="art1",
            document_id="doc1",
            artifact_type=ArtifactType.IMAGE,
            storage_path="p.png",
        )
    )
    repo.set_chunk_id("art1", "chunk1")
    fetched = repo.get_by_id("art1")
    assert fetched is not None
    assert fetched.chunk_id == "chunk1"
    linked = repo.get_for_chunk("chunk1")
    assert linked is not None
    assert linked.id == "art1"


def test_artifact_list_for_document(db_conn: sqlite3.Connection) -> None:
    _make_document(db_conn)
    repo = ArtifactRepository(db_conn)
    repo.create(
        Artifact(id="a1", document_id="doc1", artifact_type=ArtifactType.IMAGE, storage_path="p1")
    )
    repo.create(
        Artifact(id="a2", document_id="doc1", artifact_type=ArtifactType.AUDIO, storage_path="p2")
    )
    artifacts = repo.list_for_document("doc1")
    assert {a.id for a in artifacts} == {"a1", "a2"}


def test_chunk_repository_round_trips_phase4_fields(db_conn: sqlite3.Connection) -> None:
    _make_document(db_conn)
    chunk_repo = ChunkRepository(db_conn)
    chunk = Chunk(
        id="doc1::chunk::00000",
        document_id="doc1",
        order=0,
        chunk_type=BlockType.IMAGE,
        content="A diagram showing X. Some OCR text.",
        ocr_text="Some OCR text.",
        ocr_status=VisionStatus.AVAILABLE,
        vlm_description="A diagram showing X.",
        vision_status=VisionStatus.AVAILABLE,
        artifact_id="art1",
    )
    chunk_repo.replace_for_document("doc1", [chunk])

    fetched = chunk_repo.get_by_id("doc1::chunk::00000")
    assert fetched is not None
    assert fetched.ocr_text == "Some OCR text."
    assert fetched.vlm_description == "A diagram showing X."
    assert fetched.vision_status == VisionStatus.AVAILABLE
    assert fetched.artifact_id == "art1"


def test_chunk_repository_round_trips_transcript_timestamps(db_conn: sqlite3.Connection) -> None:
    _make_document(db_conn)
    chunk_repo = ChunkRepository(db_conn)
    chunk = Chunk(
        id="doc1::chunk::00000",
        document_id="doc1",
        order=0,
        chunk_type=BlockType.TRANSCRIPT,
        content="Welcome to lecture one.",
        audio_start=0.0,
        audio_end=2.5,
    )
    chunk_repo.replace_for_document("doc1", [chunk])
    fetched = chunk_repo.get_by_id("doc1::chunk::00000")
    assert fetched is not None
    assert fetched.audio_start == 0.0
    assert fetched.audio_end == 2.5
    assert fetched.chunk_type == BlockType.TRANSCRIPT


def test_chunk_repository_get_by_id_missing_returns_none(db_conn: sqlite3.Connection) -> None:
    assert ChunkRepository(db_conn).get_by_id("nonexistent") is None
