"""Golden/snapshot test for study_notes.html.

HTML is used here (rather than PDF) because Docling's HTML backend is
format-native, not ML-based, so its output is fully deterministic across
machines/runs — a requirement for a meaningful snapshot. If this test
starts failing, either parsing or chunking behavior changed: update the
expectation deliberately, don't just make the assertion pass.
"""

from pathlib import Path

from app.ingestion.chunking import ChunkingConfig, chunk_document
from app.ingestion.parsers.docling_parser import DoclingParser
from app.ingestion.storage import DataPaths, FileImageStorage

EXPECTED_BLOCK_TYPES = [
    "heading",  # Chapter 1: Cell Biology
    "heading",  # Section 1.1: Photosynthesis
    "paragraph",
    "paragraph",
    "list",
    "list",
    "list",
    "table",
    "heading",  # Section 1.2: Cellular Respiration
    "paragraph",
    "image",
    "caption",
]

EXPECTED_SECTIONS = [
    "Chapter 1: Cell Biology",
    "Section 1.1: Photosynthesis",
    "Section 1.1: Photosynthesis",
    "Section 1.1: Photosynthesis",
    "Section 1.1: Photosynthesis",
    "Section 1.1: Photosynthesis",
    "Section 1.1: Photosynthesis",
    "Section 1.1: Photosynthesis",
    "Section 1.2: Cellular Respiration",
    "Section 1.2: Cellular Respiration",
    "Section 1.2: Cellular Respiration",
    "Section 1.2: Cellular Respiration",
]


def test_html_fixture_parses_to_the_expected_block_structure(
    fixtures_dir: Path, tmp_path: Path
) -> None:
    paths = DataPaths(str(tmp_path))
    parser = DoclingParser(image_storage=FileImageStorage(paths))
    doc = parser.parse(
        fixtures_dir / "study_notes.html",
        document_id="golden-doc",
        filename="study_notes.html",
        file_hash="golden-hash",
    )

    assert [b.type.value for b in doc.blocks] == EXPECTED_BLOCK_TYPES
    assert [b.section for b in doc.blocks] == EXPECTED_SECTIONS
    assert doc.metadata.title == "Chapter 1: Cell Biology"


def test_html_fixture_chunking_is_stable(fixtures_dir: Path, tmp_path: Path) -> None:
    paths = DataPaths(str(tmp_path))
    parser = DoclingParser(image_storage=FileImageStorage(paths))
    doc = parser.parse(
        fixtures_dir / "study_notes.html",
        document_id="golden-doc",
        filename="study_notes.html",
        file_hash="golden-hash",
    )
    config = ChunkingConfig(target_tokens=512, overlap_tokens=50)
    chunks = chunk_document(doc.id, doc.blocks, config)

    # With the 512-token baseline target, every block in this small fixture
    # fits in a single text run per section. Three section groups (the H1
    # "Chapter 1" heading is itself a one-block section before "Section
    # 1.1" begins) each get one parent chunk plus their child chunk(s).
    chunk_types = [c.chunk_type.value for c in chunks]
    assert chunk_types == [
        "heading",  # Chapter 1 parent (its own section, no children)
        "paragraph",  # Chapter 1 text run
        "heading",  # Section 1.1 parent
        "paragraph",  # Section 1.1 text run
        "table",
        "heading",  # Section 1.2 parent
        "paragraph",  # Section 1.2 text run
        "image",
        "caption",
    ]

    parent_ids = {c.id for c in chunks if c.parent_id is None}
    assert len(parent_ids) == 3  # one synthetic section chunk per heading encountered
    for chunk in chunks:
        if chunk.parent_id is not None:
            assert chunk.parent_id in parent_ids
