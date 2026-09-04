"""Docling-backed implementation of :class:`~app.ingestion.parsers.base.DocumentParser`.

Docling is the primary parser per the EduRAG baseline (README §6). This
module is the *only* place in the application allowed to import
``docling``/``docling_core`` directly — everything else consumes the
canonical model in :mod:`app.ingestion.models` (ADR-004).

Known limitations (documented rather than silently worked around):

- Docling's default PDF pipeline uses ML layout/OCR models; on tiny
  synthetic fixtures it can under-detect tables/lists/images compared to
  DOCX/PPTX/HTML, which use format-native (non-ML) backends. This is a
  fidelity characteristic of Docling itself, not something this adapter
  compensates for.
- Formula/equation detection requires Docling's optional formula
  enrichment model (``do_formula_enrichment``), which downloads an
  additional VLM and is not enabled here to keep local-first ingestion
  lightweight (this is the same reasoning as not doing VLM image
  understanding in Phase 1). The EQUATION block type and
  ``equation_content`` field exist end-to-end and are exercised by unit
  tests, but are not expected to trigger from our current fixtures.
- Native document metadata (author/subject/created/modified) is read
  from DOCX/PPTX core properties where present; PDF/HTML do not expose
  equivalent metadata through Docling and are left as ``None`` rather
  than guessed.
- PDF layout detection is pinned to the Heron model running on the
  ONNXRuntime engine (CPUExecutionProvider) instead of Docling's default
  Transformers/PyTorch engine. On Apple Silicon (e.g. M1 Pro, 16GB RAM),
  the Transformers/PyTorch path segfaults natively while loading the
  Heron layout model; the ONNXRuntime engine uses the same model weights
  (``docling-project/docling-layout-heron-onnx``) without that crash.
  This only affects the PDF format option; DOCX/PPTX/HTML keep Docling's
  defaults.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from docling.datamodel.base_models import InputFormat
from docling.datamodel.object_detection_engine_options import (
    OnnxRuntimeObjectDetectionEngineOptions,
)
from docling.datamodel.pipeline_options import (
    AcceleratorDevice,
    AcceleratorOptions,
    LayoutObjectDetectionOptions,
    PdfPipelineOptions,
)
from docling.datamodel.stage_model_specs import (
    EngineModelConfig,
    ObjectDetectionEngineType,
    ObjectDetectionModelSpec,
)
from docling.document_converter import DocumentConverter, PdfFormatOption
from docling_core.types.doc.document import DoclingDocument
from docling_core.types.doc.labels import DocItemLabel

from app.ingestion.errors import ParserError
from app.ingestion.models import BlockType, DocumentBlock, DocumentMetadata, ParsedDocument
from app.ingestion.storage import ImageStorage

_LABEL_TO_BLOCK_TYPE: dict[str, BlockType] = {
    DocItemLabel.TITLE.value: BlockType.HEADING,
    DocItemLabel.SECTION_HEADER.value: BlockType.HEADING,
    DocItemLabel.TEXT.value: BlockType.PARAGRAPH,
    DocItemLabel.PARAGRAPH.value: BlockType.PARAGRAPH,
    DocItemLabel.LIST_ITEM.value: BlockType.LIST,
    DocItemLabel.TABLE.value: BlockType.TABLE,
    DocItemLabel.PICTURE.value: BlockType.IMAGE,
    DocItemLabel.FORMULA.value: BlockType.EQUATION,
    DocItemLabel.CODE.value: BlockType.CODE,
    DocItemLabel.CAPTION.value: BlockType.CAPTION,
}

_SUPPORTED_FILE_TYPES = frozenset({"pdf", "docx", "pptx", "html", "htm"})


class DoclingParser:
    """Parses PDF/DOCX/PPTX/HTML into the canonical document model."""

    def __init__(self, image_storage: ImageStorage | None = None) -> None:
        self._converter = self._build_converter()
        self._image_storage = image_storage

    @staticmethod
    def _build_converter() -> DocumentConverter:
        """Build the Docling converter, pinning PDF layout to Heron/ONNXRuntime.

        Only the PDF format option is overridden; DOCX/PPTX/HTML use
        Docling's defaults untouched.
        """
        layout_options = LayoutObjectDetectionOptions(
            engine_options=OnnxRuntimeObjectDetectionEngineOptions(
                providers=["CPUExecutionProvider"]
            ),
            model_spec=ObjectDetectionModelSpec(
                name="layout_heron",
                repo_id="docling-project/docling-layout-heron",
                revision="main",
                engine_overrides={
                    ObjectDetectionEngineType.ONNXRUNTIME: EngineModelConfig(
                        repo_id="docling-project/docling-layout-heron-onnx",
                        extra_config={"model_filename": "model.onnx"},
                    )
                },
            ),
        )
        pdf_pipeline_options = PdfPipelineOptions(
            accelerator_options=AcceleratorOptions(device=AcceleratorDevice.CPU),
            layout_options=layout_options,
        )
        return DocumentConverter(
            format_options={
                InputFormat.PDF: PdfFormatOption(pipeline_options=pdf_pipeline_options)
            }
        )

    def supports(self, file_type: str) -> bool:
        return file_type.lower() in _SUPPORTED_FILE_TYPES

    def parse(
        self, file_path: Path, *, document_id: str, filename: str, file_hash: str
    ) -> ParsedDocument:
        try:
            result = self._converter.convert(str(file_path))
            doc = result.document
        except Exception as exc:  # Docling raises varied, format-specific errors.
            raise ParserError(f"Failed to parse document '{filename}'.") from exc

        if doc is None:
            raise ParserError(f"Docling returned no content for '{filename}'.")

        blocks = self._build_blocks(doc, document_id=document_id)
        if not blocks:
            raise ParserError(f"No extractable content found in '{filename}'.")

        metadata = self._build_metadata(
            doc, file_path=file_path, filename=filename, file_hash=file_hash, blocks=blocks
        )
        file_type = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""

        return ParsedDocument(
            id=document_id,
            filename=filename,
            file_hash=file_hash,
            file_type=file_type,
            metadata=metadata,
            blocks=blocks,
        )

    def _build_blocks(self, doc: DoclingDocument, *, document_id: str) -> list[DocumentBlock]:
        blocks: list[DocumentBlock] = []
        seen_refs: set[str] = set()
        heading_stack: list[tuple[int, str]] = []
        order = 0

        for item, level in doc.iterate_items():
            label = getattr(item, "label", None)
            label_value = getattr(label, "value", None) or str(label) if label else None
            block_type = _LABEL_TO_BLOCK_TYPE.get(label_value or "", BlockType.UNKNOWN)
            text = (getattr(item, "text", None) or "").strip()

            self_ref = getattr(item, "self_ref", None)
            if self_ref:
                seen_refs.add(self_ref)

            if block_type == BlockType.HEADING:
                while heading_stack and heading_stack[-1][0] >= level:
                    heading_stack.pop()
                if text:
                    heading_stack.append((level, text))

            heading_path = [heading_text for _, heading_text in heading_stack]
            section = heading_path[-1] if heading_path else None
            page = self._page_of(item)

            block = DocumentBlock(
                id=f"{document_id}::block::{order:05d}",
                type=block_type,
                content=text,
                order=order,
                page=page,
                section=section,
                heading_path=list(heading_path),
            )

            if block_type == BlockType.TABLE:
                block.table_content = self._table_grid(item)
                block.content = block.content or self._table_to_text(block.table_content)
            elif block_type == BlockType.IMAGE:
                block.image_path = self._save_image(item, doc, document_id, block.id)
            elif block_type == BlockType.EQUATION:
                block.equation_content = text

            if block_type == BlockType.UNKNOWN and not text:
                # Skip structurally-uninteresting, textless items (e.g. page
                # headers/footers) rather than emitting empty UNKNOWN blocks.
                continue

            blocks.append(block)
            order += 1

        # Docling can place pictures/tables on a layer that iterate_items()
        # does not traverse for some formats (observed for DOCX images).
        # Recover anything missed rather than silently dropping it.
        for picture in doc.pictures:
            if getattr(picture, "self_ref", None) in seen_refs:
                continue
            block = DocumentBlock(
                id=f"{document_id}::block::{order:05d}",
                type=BlockType.IMAGE,
                content="",
                order=order,
                page=self._page_of(picture),
            )
            block.image_path = self._save_image(picture, doc, document_id, block.id)
            blocks.append(block)
            order += 1

        for table in doc.tables:
            if getattr(table, "self_ref", None) in seen_refs:
                continue
            grid = self._table_grid(table)
            block = DocumentBlock(
                id=f"{document_id}::block::{order:05d}",
                type=BlockType.TABLE,
                content=self._table_to_text(grid),
                order=order,
                page=self._page_of(table),
                table_content=grid,
            )
            blocks.append(block)
            order += 1

        return blocks

    @staticmethod
    def _page_of(item: object) -> int | None:
        prov = getattr(item, "prov", None)
        if prov:
            return int(prov[0].page_no)
        return None

    @staticmethod
    def _table_grid(item: object) -> list[list[str]] | None:
        data = getattr(item, "data", None)
        grid = getattr(data, "grid", None) if data is not None else None
        if not grid:
            return None
        return [[cell.text for cell in row] for row in grid]

    @staticmethod
    def _table_to_text(grid: list[list[str]] | None) -> str:
        if not grid:
            return ""
        return "; ".join(" | ".join(cell for cell in row) for row in grid)

    def _save_image(
        self, picture_item: object, doc: DoclingDocument, document_id: str, block_id: str
    ) -> str | None:
        if self._image_storage is None:
            return None
        get_image = getattr(picture_item, "get_image", None)
        if get_image is None:
            return None
        try:
            pil_image = get_image(doc)
        except Exception:
            return None
        if pil_image is None:
            return None
        return self._image_storage.save(document_id, block_id, pil_image)

    def _build_metadata(
        self,
        doc: DoclingDocument,
        *,
        file_path: Path,
        filename: str,
        file_hash: str,
        blocks: list[DocumentBlock],
    ) -> DocumentMetadata:
        title = next((b.content for b in blocks if b.type == BlockType.HEADING), None)
        page_count = doc.num_pages() or None

        author: str | None = None
        subject: str | None = None
        created_at = None
        modified_at = None

        file_type = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
        native = _read_native_metadata(file_path, file_type)
        if native is not None:
            title = native.title or title
            author = native.author
            subject = native.subject
            created_at = native.created_at
            modified_at = native.modified_at

        return DocumentMetadata(
            title=title,
            author=author,
            subject=subject,
            created_at=created_at,
            modified_at=modified_at,
            page_count=page_count,
            source_filename=filename,
            file_hash=file_hash,
        )


@dataclass
class _NativeMetadata:
    title: str | None
    author: str | None
    subject: str | None
    created_at: datetime | None
    modified_at: datetime | None


def _read_native_metadata(file_path: Path, file_type: str) -> _NativeMetadata | None:
    """Best-effort native metadata extraction for formats that carry it.

    Implementation choice: Docling does not surface DOCX/PPTX core
    properties on its canonical document, so we read them directly from
    the source file using the same libraries Docling already depends on.
    PDF/HTML have no equivalent standard property set here and are left
    as ``None`` rather than approximated.
    """
    try:
        if file_type == "docx":
            import docx

            props = docx.Document(str(file_path)).core_properties
            return _NativeMetadata(
                title=props.title or None,
                author=props.author or None,
                subject=props.subject or None,
                created_at=props.created,
                modified_at=props.modified,
            )
        if file_type == "pptx":
            from pptx import Presentation

            props = Presentation(str(file_path)).core_properties
            return _NativeMetadata(
                title=props.title or None,
                author=props.author or None,
                subject=props.subject or None,
                created_at=props.created,
                modified_at=props.modified,
            )
    except Exception:
        return None
    return None
