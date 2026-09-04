"""Enriched multimodal chunks flowing through the existing Phase 2
BM25/dense retrieval pipeline unchanged — no second retrieval system."""

from __future__ import annotations

from app.ingestion.models import BlockType, Chunk, VisionStatus
from app.retrieval.bm25_retriever import BM25Retriever
from app.retrieval.corpus import chunk_metadata, eligible_chunks


def _image_chunk(enriched: bool) -> Chunk:
    if not enriched:
        return Chunk(
            id="c1",
            document_id="doc1",
            order=0,
            chunk_type=BlockType.IMAGE,
            content="",
            image_path="p.png",
        )
    return Chunk(
        id="c1",
        document_id="doc1",
        order=0,
        chunk_type=BlockType.IMAGE,
        content="A diagram of the CPU pipeline. Fetch, decode, execute.",
        image_path="p.png",
        ocr_text="Fetch, decode, execute.",
        ocr_status=VisionStatus.AVAILABLE,
        vlm_description="A diagram of the CPU pipeline.",
        vision_status=VisionStatus.AVAILABLE,
    )


def test_unenriched_image_chunk_is_excluded_from_indexing() -> None:
    assert eligible_chunks([_image_chunk(enriched=False)]) == []


def test_enriched_image_chunk_is_eligible_for_indexing() -> None:
    eligible = eligible_chunks([_image_chunk(enriched=True)])
    assert len(eligible) == 1
    assert eligible[0].id == "c1"


def test_enriched_image_chunk_is_retrievable_via_bm25() -> None:
    text_chunk = Chunk(
        id="c2",
        document_id="doc1",
        order=1,
        chunk_type=BlockType.PARAGRAPH,
        content="Unrelated text about biology.",
    )
    retriever = BM25Retriever.from_chunks([_image_chunk(enriched=True), text_chunk])
    results = retriever.retrieve("CPU pipeline fetch decode execute", top_k=5)
    assert results
    assert results[0].chunk_id == "c1"


def test_chunk_metadata_carries_vlm_and_ocr_fields() -> None:
    metadata = chunk_metadata(_image_chunk(enriched=True))
    assert metadata["chunk_type"] == "image"
    assert metadata["ocr_text"] == "Fetch, decode, execute."
    assert metadata["vlm_description"] == "A diagram of the CPU pipeline."
    assert metadata["vision_status"] == "available"
    assert metadata["original_artifact"] == "p.png"


def test_chunk_metadata_carries_transcript_timestamps() -> None:
    chunk = Chunk(
        id="c3",
        document_id="doc1",
        order=0,
        chunk_type=BlockType.TRANSCRIPT,
        content="Welcome to lecture one.",
        audio_start=751.0,
        audio_end=788.0,
    )
    metadata = chunk_metadata(chunk)
    assert metadata["chunk_type"] == "transcript"
    assert metadata["audio_start"] == 751.0
    assert metadata["audio_end"] == 788.0


def test_chunk_metadata_carries_table_content() -> None:
    chunk = Chunk(
        id="c4",
        document_id="doc1",
        order=0,
        chunk_type=BlockType.TABLE,
        content="Year | Revenue; 2024 | 150",
        table_content=[["Year", "Revenue"], ["2024", "150"]],
    )
    metadata = chunk_metadata(chunk)
    assert metadata["table_content"] == [["Year", "Revenue"], ["2024", "150"]]


def test_chunk_metadata_omits_unset_multimodal_fields_for_plain_text() -> None:
    chunk = Chunk(
        id="c5", document_id="doc1", order=0, chunk_type=BlockType.PARAGRAPH, content="Plain text."
    )
    metadata = chunk_metadata(chunk)
    assert set(metadata.keys()) == {"chunk_type"}
