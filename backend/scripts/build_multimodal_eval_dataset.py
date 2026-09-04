"""Print the deterministic chunk ids for `app/multimodal/evaluation/dataset.json`.

Mirrors `scripts/build_eval_dataset.py`'s discipline for Phase 2: this
script derives chunk ids by actually running ingestion (with a *mocked*
vision/OCR provider — no real VLM/OCR model is available in this
environment, see docs/research/reproducibility.md) and a real audio
pipeline (mocked transcription, same reason) against small deterministic
fixtures, and prints them so `dataset.json` can be updated deliberately.
It does not write `dataset.json` itself.

Run from `backend/`: `uv run python scripts/build_multimodal_eval_dataset.py`
"""

from __future__ import annotations

import io
import wave
from pathlib import Path

from app.ingestion.chunking import ChunkingConfig
from app.ingestion.hashing import sha256_bytes
from app.ingestion.parsers.docling_parser import DoclingParser
from app.ingestion.repository import ChunkRepository, DocumentRepository, get_connection, init_db
from app.ingestion.service import IngestionService
from app.ingestion.storage import DataPaths, FileImageStorage
from app.multimodal.audio_chunking import chunk_transcript
from app.multimodal.image_processing import ImageEnrichmentService
from app.multimodal.models import TranscriptSegment
from app.multimodal.repository import ArtifactRepository

FIXTURES_DIR = Path(__file__).resolve().parents[1] / "tests" / "fixtures"
SCRATCH = Path("/tmp/build_multimodal_eval_dataset_scratch")


class _MockVisionProvider:
    def is_available(self) -> bool:
        return True

    def describe(self, image_path: Path, *, context: str = ""):  # type: ignore[no-untyped-def]
        from app.ingestion.models import VisionStatus
        from app.multimodal.models import VisionDescription

        return VisionDescription(
            status=VisionStatus.AVAILABLE,
            description="A labeled diagram of a plant cell showing the nucleus, "
            "mitochondria, and chloroplast.",
            model="mock-vlm",
        )

    @property
    def model_id(self) -> str:
        return "mock-vlm"


class _MockOCRProvider:
    def is_available(self) -> bool:
        return True

    def extract(self, image_path: Path):  # type: ignore[no-untyped-def]
        from app.ingestion.models import VisionStatus
        from app.multimodal.models import OCRResult

        return OCRResult(
            status=VisionStatus.AVAILABLE, text="Figure 1: Plant Cell", engine="mock-ocr"
        )

    @property
    def engine_id(self) -> str:
        return "mock-ocr"


def _build_document_dataset() -> None:
    SCRATCH.mkdir(exist_ok=True)
    data_paths = DataPaths(str(SCRATCH / "data"))
    conn = get_connection(str(SCRATCH / "app.db"))
    init_db(conn)
    artifact_repo = ArtifactRepository(conn)

    parser = DoclingParser(image_storage=FileImageStorage(data_paths))
    enricher = ImageEnrichmentService(
        vision_provider=_MockVisionProvider(),  # type: ignore[arg-type]
        ocr_provider=_MockOCRProvider(),  # type: ignore[arg-type]
        artifact_repo=artifact_repo,
        data_paths=data_paths,
        max_image_size_bytes=20 * 1024 * 1024,
        max_image_pixels=40_000_000,
    )
    service = IngestionService(
        parser=parser,
        document_repo=DocumentRepository(conn),
        chunk_repo=ChunkRepository(conn),
        data_paths=data_paths,
        supported_extensions=("pdf", "docx", "pptx", "html", "htm"),
        max_upload_size_bytes=50 * 1024 * 1024,
        chunking_config=ChunkingConfig(target_tokens=512, overlap_tokens=50),
        image_enricher=enricher,
        artifact_repo=artifact_repo,
    )

    data = (FIXTURES_DIR / "study_notes.docx").read_bytes()
    result = service.ingest("study_notes.docx", data)
    print(f"=== study_notes.docx document_id={result.document_id} (mocked VLM/OCR) ===")
    for chunk in ChunkRepository(conn).list_for_document(result.document_id):
        preview = chunk.content[:80].replace("\n", "\\n")
        print(f"  {chunk.id}  [{chunk.chunk_type.value}]  {preview!r}")
    print()


def _build_audio_dataset() -> None:
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(16000)
        wav_file.writeframes(b"\x00\x00" * 1600)
    wav_bytes = buffer.getvalue()
    document_id = sha256_bytes(wav_bytes)

    segments = [
        TranscriptSegment(text="Welcome to lecture one on cell biology.", start=0.0, end=4.0),
        TranscriptSegment(
            text="Today we will discuss the structure of the plant cell.", start=4.0, end=9.5
        ),
    ]
    chunks = chunk_transcript(document_id, segments, target_tokens=512)
    print(f"=== mock_lecture.wav document_id={document_id} (mocked transcription) ===")
    for chunk in chunks:
        print(
            f"  {chunk.id}  [transcript]  start={chunk.audio_start} end={chunk.audio_end}  "
            f"{chunk.content!r}"
        )


if __name__ == "__main__":
    _build_document_dataset()
    _build_audio_dataset()
