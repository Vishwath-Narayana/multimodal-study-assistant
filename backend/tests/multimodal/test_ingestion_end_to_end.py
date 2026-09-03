"""End-to-end: artifact -> multimodal chunk -> retrieval-eligible content,
via the real IngestionService + ImageEnrichmentService wiring (spec section
40.12's required trace, minus the generation/citation leg already covered
by test_citations_multimodal.py)."""

from __future__ import annotations

from pathlib import Path

from app.ingestion.chunking import ChunkingConfig
from app.ingestion.models import BlockType, VisionStatus
from app.ingestion.parsers.docling_parser import DoclingParser
from app.ingestion.repository import ChunkRepository, DocumentRepository, get_connection, init_db
from app.ingestion.service import IngestionService
from app.ingestion.storage import DataPaths, FileImageStorage
from app.multimodal.image_processing import ImageEnrichmentService
from app.multimodal.repository import ArtifactRepository
from app.retrieval.corpus import eligible_chunks
from tests.multimodal.fakes import FakeOCRProvider, FakeVisionProvider


def test_image_enrichment_wired_into_ingestion_produces_eligible_chunk(
    ingestion_env: Path, fixtures_dir: Path
) -> None:
    from app.core.config import get_settings

    settings = get_settings()
    data_paths = DataPaths(settings.data_dir)
    image_storage = FileImageStorage(data_paths)
    parser = DoclingParser(image_storage=image_storage)

    conn = get_connection(settings.sqlite_path)
    init_db(conn)
    artifact_repo = ArtifactRepository(conn)

    image_enricher = ImageEnrichmentService(
        vision_provider=FakeVisionProvider(description="A labeled cell diagram."),
        ocr_provider=FakeOCRProvider(text="Nucleus"),
        artifact_repo=artifact_repo,
        data_paths=data_paths,
        max_image_size_bytes=10_000_000,
        max_image_pixels=10_000_000,
    )

    service = IngestionService(
        parser=parser,
        document_repo=DocumentRepository(conn),
        chunk_repo=ChunkRepository(conn),
        data_paths=data_paths,
        supported_extensions=("pdf", "docx", "pptx", "html", "htm"),
        max_upload_size_bytes=settings.max_upload_size_mb * 1024 * 1024,
        chunking_config=ChunkingConfig(
            target_tokens=settings.chunk_target_tokens, overlap_tokens=settings.chunk_overlap_tokens
        ),
        image_enricher=image_enricher,
        artifact_repo=artifact_repo,
    )

    result = service.ingest("study_notes.docx", (fixtures_dir / "study_notes.docx").read_bytes())
    assert result.status == "completed"

    chunks = ChunkRepository(conn).list_for_document(result.document_id)
    image_chunks = [c for c in chunks if c.chunk_type == BlockType.IMAGE]
    assert len(image_chunks) == 1
    image_chunk = image_chunks[0]

    # 1. Original visual evidence preserved.
    assert image_chunk.image_path is not None
    # 2. Derived analysis attached, never overwriting the original.
    assert image_chunk.vlm_description == "A labeled cell diagram."
    assert image_chunk.ocr_text == "Nucleus"
    assert image_chunk.vision_status == VisionStatus.AVAILABLE
    # 3. Combined searchable text -> eligible for BM25/FAISS indexing.
    assert eligible_chunks([image_chunk]) == [image_chunk]

    # 4. Provenance chain: chunk -> artifact -> original image, fully linked
    #    (no orphaned artifact left behind after ingestion completes).
    assert image_chunk.artifact_id is not None
    artifact = artifact_repo.get_by_id(image_chunk.artifact_id)
    assert artifact is not None
    assert artifact.chunk_id == image_chunk.id
    assert artifact.storage_path == image_chunk.image_path


def test_ingestion_without_image_enricher_behaves_like_phase1(
    ingestion_service: IngestionService, fixtures_dir: Path
) -> None:
    """No image_enricher configured (the default) -> unchanged Phase 1/2/3
    behavior: image chunks are kept but not analyzed or indexed."""
    result = ingestion_service.ingest(
        "study_notes.docx", (fixtures_dir / "study_notes.docx").read_bytes()
    )
    assert result.status == "completed"
