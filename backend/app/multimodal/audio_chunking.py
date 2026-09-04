"""Timestamp-aware transcript chunking (spec section 16).

Groups Whisper-style segments into ~`target_tokens` chunks, the same token
budget `app.ingestion.chunking` uses for text, but is otherwise a distinct,
audio-specific algorithm: PDF chunking rules (section/heading grouping,
parent chunks, overlap) do not apply to a flat segment stream (spec: "do
not blindly apply PDF chunking rules to audio"). Each resulting chunk
retains `audio_start`/`audio_end` spanning its first/last segment, so an
answer can always be traced back to `audio_start -> audio_end -> original
lecture audio` (spec section 16).
"""

from __future__ import annotations

from app.ingestion.chunking import approx_token_count
from app.ingestion.models import BlockType, Chunk
from app.multimodal.models import TranscriptSegment


def chunk_transcript(
    document_id: str,
    segments: list[TranscriptSegment],
    *,
    target_tokens: int,
) -> list[Chunk]:
    """No overlap between transcript chunks (unlike text chunking): the
    original audio timestamps already let a reader step to the adjacent
    chunk directly, so repeating trailing words across a chunk boundary
    would only duplicate retrieval content without adding useful context —
    an implementation choice documented in docs/architecture/multimodal.md.
    """
    chunks: list[Chunk] = []
    current: list[TranscriptSegment] = []
    current_tokens = 0
    order = 0

    def flush() -> None:
        nonlocal current, current_tokens, order
        if not current:
            return
        text = " ".join(s.text for s in current if s.text)
        chunks.append(
            Chunk(
                id=f"{document_id}::chunk::{order:05d}",
                document_id=document_id,
                order=order,
                chunk_type=BlockType.TRANSCRIPT,
                content=text,
                token_count=approx_token_count(text),
                audio_start=current[0].start,
                audio_end=current[-1].end,
            )
        )
        order += 1
        current = []
        current_tokens = 0

    for segment in segments:
        segment_tokens = approx_token_count(segment.text)
        if current and current_tokens + segment_tokens > target_tokens:
            flush()
        current.append(segment)
        current_tokens += segment_tokens

    flush()
    return chunks
