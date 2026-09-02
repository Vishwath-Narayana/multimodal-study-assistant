"""Persistence round-trips for documents and chunks."""

from pathlib import Path

from app.ingestion.models import BlockType, Chunk
from app.ingestion.repository import (
    ChunkRepository,
    DocumentRepository,
    DocumentUpsert,
    get_connection,
    init_db,
)


def test_document_upsert_and_get_by_id(tmp_path: Path) -> None:
    conn = get_connection(str(tmp_path / "test.db"))
    init_db(conn)
    repo = DocumentRepository(conn)

    stored = repo.upsert(
        DocumentUpsert(
            id="doc1", filename="a.pdf", file_type="pdf", file_hash="hash1", status="completed"
        )
    )
    assert stored.id == "doc1"
    assert repo.get_by_id("doc1") is not None
    assert repo.get_by_hash("hash1").id == "doc1"


def test_document_upsert_preserves_uploaded_at_across_updates(tmp_path: Path) -> None:
    conn = get_connection(str(tmp_path / "test.db"))
    init_db(conn)
    repo = DocumentRepository(conn)

    repo.upsert(
        DocumentUpsert(
            id="doc1", filename="a.pdf", file_type="pdf", file_hash="hash1", status="processing"
        )
    )
    first = repo.get_by_id("doc1")
    repo.upsert(
        DocumentUpsert(
            id="doc1",
            filename="a.pdf",
            file_type="pdf",
            file_hash="hash1",
            status="completed",
            chunk_count=5,
        )
    )
    second = repo.get_by_id("doc1")
    assert first.uploaded_at == second.uploaded_at
    assert second.status == "completed"
    assert second.chunk_count == 5


def test_list_documents_orders_most_recent_first(tmp_path: Path) -> None:
    conn = get_connection(str(tmp_path / "test.db"))
    init_db(conn)
    repo = DocumentRepository(conn)
    for i in range(3):
        repo.upsert(
            DocumentUpsert(
                id=f"doc{i}",
                filename=f"{i}.pdf",
                file_type="pdf",
                file_hash=f"hash{i}",
                status="completed",
            )
        )
    documents = repo.list_documents()
    assert len(documents) == 3


def test_chunk_replace_for_document_round_trips(tmp_path: Path) -> None:
    conn = get_connection(str(tmp_path / "test.db"))
    init_db(conn)
    DocumentRepository(conn).upsert(
        DocumentUpsert(
            id="doc1", filename="a.pdf", file_type="pdf", file_hash="hash1", status="completed"
        )
    )
    chunk_repo = ChunkRepository(conn)
    chunks = [
        Chunk(
            id="doc1::chunk::00000",
            document_id="doc1",
            order=0,
            chunk_type=BlockType.PARAGRAPH,
            content="Hello world",
            section="Intro",
            heading_path=["Intro"],
            token_count=2,
        ),
        Chunk(
            id="doc1::chunk::00001",
            document_id="doc1",
            order=1,
            chunk_type=BlockType.TABLE,
            content="A | B",
            table_content=[["A", "B"]],
            token_count=1,
        ),
    ]
    chunk_repo.replace_for_document("doc1", chunks)

    fetched = chunk_repo.list_for_document("doc1")
    assert [c.id for c in fetched] == ["doc1::chunk::00000", "doc1::chunk::00001"]
    assert fetched[1].table_content == [["A", "B"]]
    assert fetched[0].heading_path == ["Intro"]


def test_chunk_replace_for_document_clears_stale_chunks(tmp_path: Path) -> None:
    conn = get_connection(str(tmp_path / "test.db"))
    init_db(conn)
    DocumentRepository(conn).upsert(
        DocumentUpsert(
            id="doc1", filename="a.pdf", file_type="pdf", file_hash="hash1", status="completed"
        )
    )
    chunk_repo = ChunkRepository(conn)
    first_chunk = Chunk(
        id="doc1::chunk::00000",
        document_id="doc1",
        order=0,
        chunk_type=BlockType.PARAGRAPH,
        content="Version one",
        token_count=2,
    )
    chunk_repo.replace_for_document("doc1", [first_chunk])
    assert len(chunk_repo.list_for_document("doc1")) == 1

    replacement_chunk = Chunk(
        id="doc1::chunk::00000",
        document_id="doc1",
        order=0,
        chunk_type=BlockType.PARAGRAPH,
        content="Version two",
        token_count=2,
    )
    chunk_repo.replace_for_document("doc1", [replacement_chunk])
    fetched = chunk_repo.list_for_document("doc1")
    assert len(fetched) == 1
    assert fetched[0].content == "Version two"
