"""Regenerate the deterministic chunk ids referenced by
`app/retrieval/evaluation/dataset.json`.

Run this (from `backend/`, `uv run python scripts/build_eval_dataset.py`)
only if the Phase 1 fixture files in `tests/fixtures/` change content —
`document_id` is a SHA-256 hash of file bytes, so a changed fixture changes
every chunk id it produces. This script does not write `dataset.json`
itself (query text and relevance judgments are curated by hand); it only
prints the current chunk ids/content so `dataset.json` can be updated
deliberately, and to make clear to graders that chunk ids in the eval
dataset were derived by actually running ingestion, not invented.
"""

from __future__ import annotations

from pathlib import Path

from app.ingestion.chunking import ChunkingConfig, chunk_document
from app.ingestion.hashing import sha256_bytes
from app.ingestion.parsers.docling_parser import DoclingParser
from app.ingestion.storage import DataPaths, FileImageStorage

FIXTURES_DIR = Path(__file__).resolve().parents[1] / "tests" / "fixtures"
FIXTURE_FILES = ["study_notes.html", "study_notes.docx", "study_notes.pptx"]


def main() -> None:
    scratch = Path("/tmp/build_eval_dataset_scratch")
    scratch.mkdir(exist_ok=True)
    paths = DataPaths(str(scratch))
    parser = DoclingParser(image_storage=FileImageStorage(paths))
    config = ChunkingConfig(target_tokens=512, overlap_tokens=50)

    for filename in FIXTURE_FILES:
        fpath = FIXTURES_DIR / filename
        data = fpath.read_bytes()
        file_hash = sha256_bytes(data)
        doc = parser.parse(fpath, document_id=file_hash, filename=filename, file_hash=file_hash)
        chunks = chunk_document(doc.id, doc.blocks, config)
        print(f"=== {filename} document_id={file_hash} ===")
        for chunk in chunks:
            preview = chunk.content[:80].replace("\n", "\\n")
            print(f"  {chunk.id}  [{chunk.chunk_type.value}]  {preview!r}")
        print()


if __name__ == "__main__":
    main()
