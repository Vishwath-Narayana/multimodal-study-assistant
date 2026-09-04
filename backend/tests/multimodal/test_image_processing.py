from __future__ import annotations

import sqlite3
from pathlib import Path

from PIL import Image

from app.ingestion.models import BlockType, DocumentBlock, VisionStatus
from app.ingestion.repository import DocumentRepository, DocumentUpsert
from app.ingestion.storage import DataPaths
from app.multimodal.image_processing import ImageEnrichmentService
from app.multimodal.repository import ArtifactRepository
from tests.multimodal.fakes import FakeOCRProvider, FakeVisionProvider


def _make_block(image_path: str, section: str | None = "Chapter 1") -> DocumentBlock:
    return DocumentBlock(
        id="doc1::block::00003",
        type=BlockType.IMAGE,
        content="",
        order=3,
        page=2,
        section=section,
        image_path=image_path,
    )


def _service(
    db_conn: sqlite3.Connection,
    data_paths: DataPaths,
    *,
    vision: FakeVisionProvider,
    ocr: FakeOCRProvider,
) -> ImageEnrichmentService:
    return ImageEnrichmentService(
        vision_provider=vision,
        ocr_provider=ocr,
        artifact_repo=ArtifactRepository(db_conn),
        data_paths=data_paths,
        max_image_size_bytes=10_000_000,
        max_image_pixels=10_000_000,
    )


def _upsert_doc(conn: sqlite3.Connection, document_id: str = "doc1") -> None:
    DocumentRepository(conn).upsert(
        DocumentUpsert(
            id=document_id,
            filename="f.pdf",
            file_type="pdf",
            file_hash=document_id,
            status="processing",
        )
    )


def _save_image(data_paths: DataPaths, document_id: str, block_id: str) -> str:
    target = data_paths.image_path(document_id, block_id)
    target.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (20, 20), color="green").save(target, format="PNG")
    return str(target.relative_to(data_paths.root))


def test_enrich_combines_vlm_description_ocr_and_context(
    db_conn: sqlite3.Connection, tmp_path: Path
) -> None:
    _upsert_doc(db_conn)
    data_paths = DataPaths(str(tmp_path / "data"))
    rel_path = _save_image(data_paths, "doc1", "doc1::block::00003")
    block = _make_block(rel_path)

    service = _service(
        db_conn,
        data_paths,
        vision=FakeVisionProvider(description="Three connected boxes."),
        ocr=FakeOCRProvider(text="Figure 1"),
    )
    enriched = service.enrich("doc1", block)

    assert enriched.vision_status == VisionStatus.AVAILABLE
    assert enriched.ocr_status == VisionStatus.AVAILABLE
    assert enriched.vlm_description == "Three connected boxes."
    assert enriched.ocr_text == "Figure 1"
    assert "Three connected boxes." in enriched.content
    assert "Figure 1" in enriched.content
    assert "Chapter 1" in enriched.content
    # Original artifact reference must be preserved untouched.
    assert enriched.image_path == rel_path
    assert enriched.artifact_id == "doc1::artifact::doc1::block::00003"

    assert enriched.artifact_id is not None
    artifact = ArtifactRepository(db_conn).get_by_id(enriched.artifact_id)
    assert artifact is not None
    assert artifact.chunk_id is None  # not yet linked — chunking hasn't run
    assert artifact.storage_path == rel_path


def test_enrich_with_unavailable_providers_leaves_content_empty(
    db_conn: sqlite3.Connection, tmp_path: Path
) -> None:
    _upsert_doc(db_conn)
    data_paths = DataPaths(str(tmp_path / "data"))
    rel_path = _save_image(data_paths, "doc1", "doc1::block::00003")
    block = _make_block(rel_path, section=None)

    service = _service(
        db_conn,
        data_paths,
        vision=FakeVisionProvider(available=False),
        ocr=FakeOCRProvider(available=False),
    )
    enriched = service.enrich("doc1", block)

    assert enriched.vision_status == VisionStatus.UNAVAILABLE
    assert enriched.ocr_status == VisionStatus.UNAVAILABLE
    assert enriched.content == ""
    assert enriched.image_path == rel_path  # original evidence still preserved


def test_enrich_block_without_image_path_is_returned_unchanged(
    db_conn: sqlite3.Connection, tmp_path: Path
) -> None:
    data_paths = DataPaths(str(tmp_path / "data"))
    block = DocumentBlock(id="b1", type=BlockType.IMAGE, content="", order=0, image_path=None)
    service = _service(db_conn, data_paths, vision=FakeVisionProvider(), ocr=FakeOCRProvider())
    result = service.enrich("doc1", block)
    assert result is block


def test_enrich_never_raises_when_oversized(db_conn: sqlite3.Connection, tmp_path: Path) -> None:
    _upsert_doc(db_conn)
    data_paths = DataPaths(str(tmp_path / "data"))
    rel_path = _save_image(data_paths, "doc1", "doc1::block::00003")
    block = _make_block(rel_path)

    service = ImageEnrichmentService(
        vision_provider=FakeVisionProvider(),
        ocr_provider=FakeOCRProvider(),
        artifact_repo=ArtifactRepository(db_conn),
        data_paths=data_paths,
        max_image_size_bytes=1,  # forces validation failure
        max_image_pixels=10_000_000,
    )
    enriched = service.enrich("doc1", block)
    # Falls back to the un-enriched block rather than raising.
    assert enriched.vision_status == VisionStatus.NOT_ATTEMPTED
    assert enriched.image_path == rel_path
