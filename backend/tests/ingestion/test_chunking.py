"""L, M, N, O: chunk size behavior, ordering, stable IDs, parent/child structure."""

from app.ingestion.chunking import ChunkingConfig, approx_token_count, chunk_document
from app.ingestion.models import BlockType, DocumentBlock


def _text_block(order: int, content: str, section: str = "Section A") -> DocumentBlock:
    return DocumentBlock(
        id=f"doc::block::{order:05d}",
        type=BlockType.PARAGRAPH,
        content=content,
        order=order,
        section=section,
        heading_path=["Chapter 1", section],
    )


def _heading_block(order: int, content: str, section: str) -> DocumentBlock:
    return DocumentBlock(
        id=f"doc::block::{order:05d}",
        type=BlockType.HEADING,
        content=content,
        order=order,
        section=section,
        heading_path=["Chapter 1", section],
    )


def test_chunks_are_non_empty() -> None:
    blocks = [_heading_block(0, "Section A", "Section A"), _text_block(1, "Some content here.")]
    chunks = chunk_document("doc", blocks, ChunkingConfig(target_tokens=512, overlap_tokens=50))
    text_chunks = [c for c in chunks if c.chunk_type != BlockType.HEADING or c.parent_id]
    assert all(c.content.strip() for c in text_chunks)


def test_chunk_ordering_matches_block_order() -> None:
    blocks = [
        _heading_block(0, "Section A", "Section A"),
        _text_block(1, "First paragraph."),
        _text_block(2, "Second paragraph."),
    ]
    chunks = chunk_document("doc", blocks, ChunkingConfig(target_tokens=512, overlap_tokens=0))
    orders = [c.order for c in chunks]
    assert orders == sorted(orders)
    assert orders == list(range(len(chunks)))


def test_chunk_size_respects_target_token_count() -> None:
    long_word_blocks = [
        _heading_block(0, "Section A", "Section A"),
        *[_text_block(i, " ".join(["word"] * 20)) for i in range(1, 6)],
    ]
    config = ChunkingConfig(target_tokens=30, overlap_tokens=0)
    chunks = chunk_document("doc", long_word_blocks, config)
    text_chunks = [c for c in chunks if c.parent_id is not None]
    # No chunk should wildly exceed the target once at least one block has
    # already been placed (a single oversized block may still exceed it —
    # we never split inside a block).
    for chunk in text_chunks:
        assert chunk.token_count <= config.target_tokens + 20  # one block's worth of slack


def test_chunk_ids_are_deterministic_for_same_input() -> None:
    blocks = [
        _heading_block(0, "Section A", "Section A"),
        _text_block(1, "First paragraph."),
        _text_block(2, "Second paragraph."),
    ]
    config = ChunkingConfig(target_tokens=512, overlap_tokens=0)
    ids_a = [c.id for c in chunk_document("doc", blocks, config)]
    ids_b = [c.id for c in chunk_document("doc", blocks, config)]
    assert ids_a == ids_b


def test_chunks_do_not_mix_unrelated_sections() -> None:
    blocks = [
        _heading_block(0, "Section A", "Section A"),
        _text_block(1, "Content about photosynthesis.", section="Section A"),
        _heading_block(2, "Section B", "Section B"),
        _text_block(3, "Content about respiration.", section="Section B"),
    ]
    chunks = chunk_document("doc", blocks, ChunkingConfig(target_tokens=512, overlap_tokens=0))
    for chunk in chunks:
        if chunk.section == "Section A":
            assert "respiration" not in chunk.content
        if chunk.section == "Section B":
            assert "photosynthesis" not in chunk.content


def test_child_chunks_reference_a_parent_section_chunk() -> None:
    blocks = [
        _heading_block(0, "Section A", "Section A"),
        _text_block(1, "First paragraph."),
        _text_block(2, "Second paragraph."),
    ]
    chunks = chunk_document("doc", blocks, ChunkingConfig(target_tokens=512, overlap_tokens=0))
    parent_chunks = [c for c in chunks if c.parent_id is None]
    child_chunks = [c for c in chunks if c.parent_id is not None]

    assert len(parent_chunks) == 1
    parent_id = parent_chunks[0].id
    assert all(c.parent_id == parent_id for c in child_chunks)


def test_table_and_image_blocks_become_their_own_chunk_not_merged_with_text() -> None:
    blocks = [
        _heading_block(0, "Section A", "Section A"),
        _text_block(1, "Intro paragraph."),
        DocumentBlock(
            id="doc::block::00002",
            type=BlockType.TABLE,
            content="A | B",
            order=2,
            section="Section A",
            table_content=[["A", "B"]],
        ),
        _text_block(3, "Trailing paragraph."),
    ]
    chunks = chunk_document("doc", blocks, ChunkingConfig(target_tokens=512, overlap_tokens=0))
    table_chunks = [c for c in chunks if c.chunk_type == BlockType.TABLE]
    assert len(table_chunks) == 1
    assert table_chunks[0].table_content == [["A", "B"]]
    assert "Intro paragraph" not in table_chunks[0].content
    assert "Trailing paragraph" not in table_chunks[0].content


def test_caption_and_code_blocks_are_not_silently_dropped() -> None:
    blocks = [
        _heading_block(0, "Section A", "Section A"),
        DocumentBlock(
            id="doc::block::00001",
            type=BlockType.IMAGE,
            content="",
            order=1,
            section="Section A",
            image_path="images/img1.png",
        ),
        DocumentBlock(
            id="doc::block::00002",
            type=BlockType.CAPTION,
            content="Figure 1: an organelle diagram",
            order=2,
            section="Section A",
        ),
        DocumentBlock(
            id="doc::block::00003",
            type=BlockType.CODE,
            content="print('hello')",
            order=3,
            section="Section A",
        ),
    ]
    chunks = chunk_document("doc", blocks, ChunkingConfig(target_tokens=512, overlap_tokens=0))
    chunk_types = {c.chunk_type for c in chunks}
    assert BlockType.CAPTION in chunk_types
    assert BlockType.CODE in chunk_types
    caption_chunk = next(c for c in chunks if c.chunk_type == BlockType.CAPTION)
    assert "organelle diagram" in caption_chunk.content


def test_approx_token_count_is_whitespace_based() -> None:
    assert approx_token_count("one two three") == 3
    assert approx_token_count("") == 0
