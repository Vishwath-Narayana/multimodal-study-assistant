from __future__ import annotations

from app.ingestion.models import BlockType, Chunk


def make_chunk(
    chunk_id: str,
    content: str,
    document_id: str = "doc-1",
    chunk_type: BlockType = BlockType.PARAGRAPH,
    page: int | None = None,
    section: str | None = None,
    parent_id: str | None = None,
) -> Chunk:
    return Chunk(
        id=chunk_id,
        document_id=document_id,
        order=0,
        chunk_type=chunk_type,
        content=content,
        page=page,
        section=section,
        parent_id=parent_id,
        token_count=len(content.split()),
    )
