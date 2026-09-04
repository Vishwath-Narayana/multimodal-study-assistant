"""I, J, K, P, Q: metadata, page metadata, section hierarchy, image/table preservation.

Known Docling limitation (see docs/architecture/ingestion.md): the default
PDF pipeline uses ML layout detection, which under-detects tables/lists/
images on tiny synthetic PDFs compared to the format-native DOCX/PPTX/HTML
backends. Table/image assertions here therefore target DOCX/PPTX/HTML;
PDF is covered separately for headings/paragraphs/page numbers, which the
layout model does detect reliably.
"""

from pathlib import Path

from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import TableFormerMode

from app.ingestion.models import BlockType
from app.ingestion.parsers.docling_parser import DoclingParser
from app.ingestion.storage import DataPaths, FileImageStorage


def test_pdf_table_structure_uses_fast_mode() -> None:
    """Table-structure recognition must stay enabled but pinned to FAST mode.

    ACCURATE mode's table-structure stage segfaults on Apple Silicon during
    a live upload even with the Heron/ONNXRuntime layout fix in place; FAST
    mode is the confirmed-stable configuration.
    """
    parser = DoclingParser()
    pdf_options = parser._converter.format_to_options[InputFormat.PDF].pipeline_options
    assert pdf_options.do_table_structure is True
    assert pdf_options.table_structure_options.mode == TableFormerMode.FAST


def _parse(fixtures_dir: Path, tmp_path: Path, filename: str):
    paths = DataPaths(str(tmp_path))
    parser = DoclingParser(image_storage=FileImageStorage(paths))
    return parser.parse(
        fixtures_dir / filename, document_id="doc-parser-test", filename=filename, file_hash="h"
    )


def test_docx_document_metadata_extracted(fixtures_dir: Path, tmp_path: Path) -> None:
    doc = _parse(fixtures_dir, tmp_path, "study_notes.docx")
    assert doc.metadata.title == "Chapter 1: Cell Biology"
    assert doc.metadata.author  # python-docx sets a default author on new docs
    assert doc.metadata.source_filename == "study_notes.docx"
    assert doc.metadata.file_hash == "h"


def test_pptx_page_metadata_present(fixtures_dir: Path, tmp_path: Path) -> None:
    doc = _parse(fixtures_dir, tmp_path, "study_notes.pptx")
    assert doc.metadata.page_count == 2
    pages = {b.page for b in doc.blocks if b.page is not None}
    assert pages == {1, 2}


def test_pdf_page_metadata_present(fixtures_dir: Path, tmp_path: Path) -> None:
    doc = _parse(fixtures_dir, tmp_path, "study_notes.pdf")
    assert doc.metadata.page_count == 2
    pages = {b.page for b in doc.blocks if b.page is not None}
    assert 1 in pages
    assert 2 in pages


def test_section_hierarchy_is_tracked(fixtures_dir: Path, tmp_path: Path) -> None:
    doc = _parse(fixtures_dir, tmp_path, "study_notes.html")
    paragraph = next(
        b
        for b in doc.blocks
        if b.type == BlockType.PARAGRAPH and "Photosynthesis converts" in b.content
    )
    assert paragraph.section == "Section 1.1: Photosynthesis"
    assert paragraph.heading_path == ["Chapter 1: Cell Biology", "Section 1.1: Photosynthesis"]

    second_section_paragraph = next(
        b
        for b in doc.blocks
        if b.type == BlockType.PARAGRAPH and "Cellular respiration" in b.content
    )
    assert second_section_paragraph.section == "Section 1.2: Cellular Respiration"


def test_docx_table_is_preserved(fixtures_dir: Path, tmp_path: Path) -> None:
    doc = _parse(fixtures_dir, tmp_path, "study_notes.docx")
    table_block = next(b for b in doc.blocks if b.type == BlockType.TABLE)
    assert table_block.table_content is not None
    assert table_block.table_content[0] == ["Organelle", "Function"]
    assert ["Mitochondria", "ATP production"] in table_block.table_content


def test_pptx_table_is_preserved(fixtures_dir: Path, tmp_path: Path) -> None:
    doc = _parse(fixtures_dir, tmp_path, "study_notes.pptx")
    table_block = next(b for b in doc.blocks if b.type == BlockType.TABLE)
    assert table_block.table_content is not None
    assert table_block.table_content[0] == ["Organelle", "Function"]


def test_docx_image_is_preserved_and_saved(fixtures_dir: Path, tmp_path: Path) -> None:
    doc = _parse(fixtures_dir, tmp_path, "study_notes.docx")
    image_block = next(b for b in doc.blocks if b.type == BlockType.IMAGE)
    assert image_block.image_path is not None
    saved_path = Path(tmp_path) / image_block.image_path
    assert saved_path.exists()
    assert saved_path.stat().st_size > 0


def test_html_image_is_structurally_detected(fixtures_dir: Path, tmp_path: Path) -> None:
    # Known Docling limitation: its HTML backend recognizes an <img> tag as
    # a PictureItem (structural detection works) but does not decode the
    # image bytes the way the DOCX/PPTX backends do, so image_path stays
    # None here. See test_docx_image_is_preserved_and_saved for the
    # byte-level preservation case, and docs/architecture/ingestion.md.
    doc = _parse(fixtures_dir, tmp_path, "study_notes.html")
    image_block = next(b for b in doc.blocks if b.type == BlockType.IMAGE)
    assert image_block is not None


def test_pdf_headings_and_paragraphs_detected(fixtures_dir: Path, tmp_path: Path) -> None:
    doc = _parse(fixtures_dir, tmp_path, "study_notes.pdf")
    types = {b.type for b in doc.blocks}
    assert BlockType.HEADING in types
    assert BlockType.PARAGRAPH in types


def test_block_ids_trace_back_to_document(fixtures_dir: Path, tmp_path: Path) -> None:
    doc = _parse(fixtures_dir, tmp_path, "study_notes.html")
    for block in doc.blocks:
        assert block.id.startswith(f"{doc.id}::block::")
