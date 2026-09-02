"""Structure-aware chunking.

EduRAG baseline: approximately 512 tokens per chunk (``chunk_target_tokens``
in :class:`app.core.config.Settings`). Chunk overlap is *not* specified by
the baseline paper — the default here is an implementation choice, kept
small relative to the target size and documented as such (see
docs/architecture/ingestion.md and docs/research/reproducibility.md).

Algorithm (deliberately simple for Phase 1):

1. Blocks are grouped by their deepest heading ("section"). A synthetic
   parent chunk is created per section so later phases have a hierarchy to
   retrieve against (README §9) — Phase 1 only builds this representation,
   it does not use it for retrieval.
2. Within a section, contiguous text-bearing blocks (heading/paragraph/
   list) are accumulated into a chunk until adding the next block would
   exceed ``chunk_target_tokens``; then a new chunk starts, seeded with the
   last ``chunk_overlap_tokens`` worth of trailing text from the previous
   chunk so semantic context is not lost at the boundary.
3. Table/image/equation blocks are never merged into a text chunk — each
   becomes its own chunk, so structured content is not fragmented or
   diluted by concatenation with unrelated prose.

Token counting is a whitespace-split approximation
(:func:`approx_token_count`), not the tokenizer of any specific embedding
model — that alignment is deferred to Phase 2 when the embedding model is
actually wired in. This is an implementation choice, not an EduRAG
requirement.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.ingestion.models import BlockType, Chunk, DocumentBlock

_TEXT_BLOCK_TYPES = frozenset({BlockType.HEADING, BlockType.PARAGRAPH, BlockType.LIST})
# Everything else gets its own dedicated chunk rather than being merged into
# surrounding prose (tables/images/equations to avoid diluting structured
# content; captions/code/unknown so nothing is silently dropped from the
# retrieval-ready output — every block must end up in exactly one chunk).
_STRUCTURED_BLOCK_TYPES = frozenset(
    {
        BlockType.TABLE,
        BlockType.IMAGE,
        BlockType.EQUATION,
        BlockType.CAPTION,
        BlockType.CODE,
        BlockType.UNKNOWN,
    }
)


def approx_token_count(text: str) -> int:
    """Whitespace-based token approximation. See module docstring."""
    return len(text.split())


@dataclass
class ChunkingConfig:
    target_tokens: int = 512
    overlap_tokens: int = 50


def chunk_document(
    document_id: str, blocks: list[DocumentBlock], config: ChunkingConfig
) -> list[Chunk]:
    """Produce retrieval-ready chunks from a canonical document's blocks."""
    chunks: list[Chunk] = []
    order = 0

    for section_key, section_blocks in _group_by_section(blocks):
        if not section_blocks:
            continue

        section = section_blocks[0].section
        heading_path = section_blocks[0].heading_path
        parent_id = f"{document_id}::section::{order:05d}"
        chunks.append(
            Chunk(
                id=parent_id,
                document_id=document_id,
                order=order,
                chunk_type=BlockType.HEADING,
                content=section or (section_key or ""),
                page=section_blocks[0].page,
                section=section,
                heading_path=list(heading_path),
                token_count=approx_token_count(section or ""),
            )
        )
        order += 1

        text_run: list[DocumentBlock] = []

        for block in section_blocks:
            if block.type in _TEXT_BLOCK_TYPES:
                text_run.append(block)
                continue

            if text_run:
                text_chunks = _split_text_run(text_run, document_id, parent_id, order, config)
                chunks.extend(text_chunks)
                order += len(text_chunks)
                text_run = []

            if block.type in _STRUCTURED_BLOCK_TYPES:
                chunks.append(_structured_chunk(block, document_id, parent_id, order))
                order += 1

        if text_run:
            text_chunks = _split_text_run(text_run, document_id, parent_id, order, config)
            chunks.extend(text_chunks)
            order += len(text_chunks)

    return chunks


def _group_by_section(
    blocks: list[DocumentBlock],
) -> list[tuple[str | None, list[DocumentBlock]]]:
    """Group blocks into contiguous runs sharing the same section.

    Contiguous (rather than a full dict-based group-by) preserves document
    order, which matters for chunk ordering and for not mixing unrelated
    sections into one chunk.
    """
    groups: list[tuple[str | None, list[DocumentBlock]]] = []
    current_key: str | None = None
    current_group: list[DocumentBlock] = []

    for block in blocks:
        key = block.section
        if not groups and not current_group:
            current_key = key
        if key != current_key:
            groups.append((current_key, current_group))
            current_group = []
            current_key = key
        current_group.append(block)

    if current_group:
        groups.append((current_key, current_group))
    return groups


def _split_text_run(
    blocks: list[DocumentBlock],
    document_id: str,
    parent_id: str,
    start_order: int,
    config: ChunkingConfig,
) -> list[Chunk]:
    """Pack a run of text-bearing blocks into ~target_tokens chunks with overlap."""
    chunks: list[Chunk] = []
    order = start_order

    current_texts: list[str] = []
    current_tokens = 0
    first_block = blocks[0]

    def make_chunk(texts: list[str]) -> Chunk:
        content = "\n".join(texts)
        return Chunk(
            id=f"{document_id}::chunk::{order:05d}",
            document_id=document_id,
            order=order,
            chunk_type=BlockType.PARAGRAPH,
            content=content,
            parent_id=parent_id,
            page=first_block.page,
            section=first_block.section,
            heading_path=list(first_block.heading_path),
            token_count=approx_token_count(content),
        )

    def overlap_tail(texts: list[str]) -> list[str]:
        if config.overlap_tokens <= 0:
            return []
        words = "\n".join(texts).split()
        tail_words = words[-config.overlap_tokens :]
        return [" ".join(tail_words)] if tail_words else []

    for block in blocks:
        block_tokens = approx_token_count(block.content)
        if current_texts and current_tokens + block_tokens > config.target_tokens:
            chunks.append(make_chunk(current_texts))
            order += 1
            current_texts = overlap_tail(current_texts)
            current_tokens = approx_token_count("\n".join(current_texts))

        current_texts.append(block.content)
        current_tokens += block_tokens

    if current_texts:
        chunks.append(make_chunk(current_texts))
        order += 1

    return chunks


def _structured_chunk(
    block: DocumentBlock, document_id: str, parent_id: str, order: int
) -> Chunk:
    return Chunk(
        id=f"{document_id}::chunk::{order:05d}",
        document_id=document_id,
        order=order,
        chunk_type=block.type,
        content=block.content,
        parent_id=parent_id,
        page=block.page,
        section=block.section,
        heading_path=list(block.heading_path),
        token_count=approx_token_count(block.content),
        image_path=block.image_path,
        table_content=block.table_content,
        equation_content=block.equation_content,
    )
