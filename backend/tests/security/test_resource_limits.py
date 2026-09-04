"""Phase 8N: resource-exhaustion security tests (spec section 8B.2/8J).

Covers the ceilings added in Phase 8: query length, `top_k`, per-document
page/extracted-text/chunk caps, and the per-document image-artifact
enrichment cap. Oversized-file and oversized-image coverage already exists
(`tests/security/test_upload_attacks.py`, `tests/multimodal/test_security.py`);
this module focuses on the *new* Phase 8 ceilings.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app.ingestion.errors import ResourceLimitExceededError
from app.ingestion.models import BlockType, DocumentBlock
from app.ingestion.repository import DocumentRepository, DocumentUpsert
from app.ingestion.storage import DataPaths
from app.multimodal.image_processing import ImageEnrichmentService
from app.multimodal.repository import ArtifactRepository
from app.retrieval.errors import InvalidTopKError, QueryTooLongError
from tests.multimodal.fakes import FakeOCRProvider, FakeVisionProvider

pytestmark = []


# --- Query / top_k (API-level, via the real retrieval choke point) ---------


def _upload_one_document(api_client: TestClient, fixtures_dir: Path) -> None:
    """These endpoints build a BM25 index from whatever is indexed
    (`app.api.retrieval.get_bm25_retriever`) — an empty corpus fails with
    `NoIndexedChunksError` before the query-length/top_k checks would ever
    run. Upload one real document first so the checks under test are what
    actually produces the 400, not an unrelated empty-corpus error."""
    with open(fixtures_dir / "study_notes.html", "rb") as f:
        response = api_client.post(
            "/documents/upload", files={"file": ("study_notes.html", f, "text/html")}
        )
    assert response.status_code == 200


def test_search_rejects_huge_query(api_client: TestClient, fixtures_dir: Path) -> None:
    _upload_one_document(api_client, fixtures_dir)
    huge_query = "x" * 100_000
    response = api_client.post(
        "/retrieval/search", json={"query": huge_query, "mode": "bm25", "top_k": 5}
    )
    assert response.status_code == 400


def test_search_rejects_out_of_range_top_k(api_client: TestClient, fixtures_dir: Path) -> None:
    _upload_one_document(api_client, fixtures_dir)
    response = api_client.post(
        "/retrieval/search", json={"query": "photosynthesis", "mode": "bm25", "top_k": 10_000}
    )
    assert response.status_code == 400


def test_search_rejects_zero_top_k(api_client: TestClient, fixtures_dir: Path) -> None:
    _upload_one_document(api_client, fixtures_dir)
    response = api_client.post(
        "/retrieval/search", json={"query": "photosynthesis", "mode": "bm25", "top_k": 0}
    )
    assert response.status_code == 400


def test_retrieval_service_error_types_map_to_400() -> None:
    """Direct unit check that the new Phase 8 error types are genuine
    `RetrievalError` subclasses picked up by the existing `_ERROR_STATUS`
    dispatch (see `app.api.retrieval`), not something that would fall
    through to an unhandled-exception 500."""
    from app.api.retrieval import _ERROR_STATUS
    from app.retrieval.errors import InvalidQueryError, RetrievalError

    assert issubclass(QueryTooLongError, RetrievalError)
    assert issubclass(InvalidTopKError, RetrievalError)
    assert issubclass(InvalidQueryError, RetrievalError)
    assert _ERROR_STATUS[QueryTooLongError] == 400
    assert _ERROR_STATUS[InvalidTopKError] == 400
    assert _ERROR_STATUS[InvalidQueryError] == 400


# --- Ingestion resource ceilings (unit-level: IngestionService) ------------


def test_document_exceeding_max_pages_is_rejected() -> None:
    from app.ingestion.service import IngestionService

    service = IngestionService.__new__(IngestionService)  # bypass __init__ wiring
    service._max_document_pages = 5
    service._max_extracted_chars = None

    from app.ingestion.models import DocumentMetadata, ParsedDocument

    parsed = ParsedDocument(
        id="doc1",
        filename="huge.pdf",
        file_hash="hash",
        file_type="pdf",
        metadata=DocumentMetadata(
            title=None,
            author=None,
            subject=None,
            created_at=None,
            modified_at=None,
            page_count=6,
            source_filename="huge.pdf",
            file_hash="hash",
        ),
        blocks=[],
    )
    with pytest.raises(ResourceLimitExceededError, match="pages"):
        service._enforce_resource_limits(parsed)


def test_document_exceeding_max_extracted_chars_is_rejected() -> None:
    from app.ingestion.models import DocumentMetadata, ParsedDocument
    from app.ingestion.service import IngestionService

    service = IngestionService.__new__(IngestionService)
    service._max_document_pages = None
    service._max_extracted_chars = 10

    parsed = ParsedDocument(
        id="doc1",
        filename="huge.pdf",
        file_hash="hash",
        file_type="pdf",
        metadata=DocumentMetadata(
            title=None,
            author=None,
            subject=None,
            created_at=None,
            modified_at=None,
            page_count=1,
            source_filename="huge.pdf",
            file_hash="hash",
        ),
        blocks=[DocumentBlock(id="b1", type=BlockType.PARAGRAPH, content="x" * 100, order=0)],
    )
    with pytest.raises(ResourceLimitExceededError, match="extracted text"):
        service._enforce_resource_limits(parsed)


def test_document_within_limits_passes() -> None:
    from app.ingestion.models import DocumentMetadata, ParsedDocument
    from app.ingestion.service import IngestionService

    service = IngestionService.__new__(IngestionService)
    service._max_document_pages = 100
    service._max_extracted_chars = 100_000

    parsed = ParsedDocument(
        id="doc1",
        filename="notes.pdf",
        file_hash="hash",
        file_type="pdf",
        metadata=DocumentMetadata(
            title=None,
            author=None,
            subject=None,
            created_at=None,
            modified_at=None,
            page_count=3,
            source_filename="notes.pdf",
            file_hash="hash",
        ),
        blocks=[DocumentBlock(id="b1", type=BlockType.PARAGRAPH, content="short text", order=0)],
    )
    service._enforce_resource_limits(parsed)  # must not raise


# --- Per-document artifact (image OCR/VLM) enrichment cap -------------------


def _make_block(image_path: str, block_id: str) -> DocumentBlock:
    return DocumentBlock(
        id=block_id, type=BlockType.IMAGE, content="", order=0, image_path=image_path
    )


def _save_image(data_paths: DataPaths, document_id: str, block_id: str) -> str:
    target = data_paths.image_path(document_id, block_id)
    target.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (10, 10), color="blue").save(target, format="PNG")
    return str(target.relative_to(data_paths.root))


def test_image_enrichment_stops_after_configured_artifact_cap(
    db_conn: sqlite3.Connection, tmp_path: Path
) -> None:
    DocumentRepository(db_conn).upsert(
        DocumentUpsert(
            id="doc1", filename="f.pdf", file_type="pdf", file_hash="doc1", status="processing"
        )
    )
    data_paths = DataPaths(str(tmp_path / "data"))
    service = ImageEnrichmentService(
        vision_provider=FakeVisionProvider(description="A diagram."),
        ocr_provider=FakeOCRProvider(text="Figure X"),
        artifact_repo=ArtifactRepository(db_conn),
        data_paths=data_paths,
        max_image_size_bytes=10_000_000,
        max_image_pixels=10_000_000,
        max_artifacts_per_document=2,
    )

    results = []
    for i in range(5):
        block_id = f"doc1::block::{i:05d}"
        rel_path = _save_image(data_paths, "doc1", block_id)
        results.append(service.enrich("doc1", _make_block(rel_path, block_id)))

    enriched = [r for r in results if r.artifact_id is not None]
    not_enriched = [r for r in results if r.artifact_id is None]
    assert len(enriched) == 2
    assert len(not_enriched) == 3
    # Original image reference is preserved even when enrichment is skipped
    # (spec section 7: never drop the original artifact).
    for r in not_enriched:
        assert r.image_path is not None
