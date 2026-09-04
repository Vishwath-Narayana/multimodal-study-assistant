from __future__ import annotations

from app.ingestion.models import BlockType
from app.multimodal.audio_chunking import chunk_transcript
from app.multimodal.models import TranscriptSegment


def test_chunk_transcript_empty_segments_returns_no_chunks() -> None:
    assert chunk_transcript("doc1", [], target_tokens=512) == []


def test_chunk_transcript_single_small_segment_becomes_one_chunk() -> None:
    segments = [TranscriptSegment(text="Hello world.", start=0.0, end=1.0)]
    chunks = chunk_transcript("doc1", segments, target_tokens=512)
    assert len(chunks) == 1
    assert chunks[0].chunk_type == BlockType.TRANSCRIPT
    assert chunks[0].content == "Hello world."
    assert chunks[0].audio_start == 0.0
    assert chunks[0].audio_end == 1.0


def test_chunk_transcript_preserves_timestamp_span_across_segments() -> None:
    segments = [
        TranscriptSegment(text="Part one.", start=0.0, end=2.0),
        TranscriptSegment(text="Part two.", start=2.0, end=4.5),
    ]
    chunks = chunk_transcript("doc1", segments, target_tokens=512)
    assert len(chunks) == 1
    assert chunks[0].audio_start == 0.0
    assert chunks[0].audio_end == 4.5
    assert chunks[0].content == "Part one. Part two."


def test_chunk_transcript_splits_on_token_budget() -> None:
    # Each 5-word segment already exceeds a target of 4, so a new segment
    # always starts a fresh chunk rather than being packed in — three
    # segments therefore produce three chunks.
    segments = [
        TranscriptSegment(text="one two three four five", start=0.0, end=1.0),
        TranscriptSegment(text="six seven eight nine ten", start=1.0, end=2.0),
        TranscriptSegment(text="eleven twelve", start=2.0, end=3.0),
    ]
    chunks = chunk_transcript("doc1", segments, target_tokens=4)
    assert len(chunks) == 3
    assert chunks[0].audio_start == 0.0
    assert chunks[0].audio_end == 1.0
    assert chunks[1].audio_start == 1.0
    assert chunks[1].audio_end == 2.0
    assert chunks[2].audio_start == 2.0
    assert chunks[2].audio_end == 3.0


def test_chunk_transcript_packs_multiple_short_segments_into_one_chunk() -> None:
    segments = [
        TranscriptSegment(text="one two", start=0.0, end=1.0),
        TranscriptSegment(text="three four", start=1.0, end=2.0),
        TranscriptSegment(text="five six seven eight nine ten", start=2.0, end=3.0),
    ]
    chunks = chunk_transcript("doc1", segments, target_tokens=6)
    assert len(chunks) == 2
    assert chunks[0].content == "one two three four"
    assert chunks[0].audio_start == 0.0
    assert chunks[0].audio_end == 2.0
    assert chunks[1].audio_start == 2.0
    assert chunks[1].audio_end == 3.0


def test_chunk_transcript_ids_are_deterministic_and_sequential() -> None:
    segments = [
        TranscriptSegment(text=f"word{i}", start=float(i), end=float(i + 1)) for i in range(3)
    ]
    chunks = chunk_transcript("doc1", segments, target_tokens=1)
    assert [c.id for c in chunks] == [
        "doc1::chunk::00000",
        "doc1::chunk::00001",
        "doc1::chunk::00002",
    ]


def test_chunk_transcript_skips_empty_segment_text() -> None:
    segments = [
        TranscriptSegment(text="", start=0.0, end=0.5),
        TranscriptSegment(text="Real words.", start=0.5, end=1.5),
    ]
    chunks = chunk_transcript("doc1", segments, target_tokens=512)
    assert len(chunks) == 1
    assert chunks[0].content == "Real words."
