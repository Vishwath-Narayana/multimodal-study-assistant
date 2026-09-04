"""Filesystem storage for uploaded documents and extracted images.

Layout (see docs/architecture/ingestion.md):

    data/
    ├── raw/<document_id>/<safe_filename>       original uploaded file
    └── processed/<document_id>/images/<id>.png  extracted images

All paths are resolved and checked against the configured data root to
prevent path traversal — uploaded filenames are untrusted input.
"""

from __future__ import annotations

import re
import shutil
from pathlib import Path
from typing import Protocol

from PIL.Image import Image

from app.ingestion.errors import StorageError

_SAFE_FILENAME_RE = re.compile(r"[^A-Za-z0-9._-]+")


def sanitize_filename(filename: str) -> str:
    """Reduce a filename to a safe basename with no path components."""
    name = Path(filename).name
    name = _SAFE_FILENAME_RE.sub("_", name).strip("._")
    return name or "upload"


def _resolve_within(root: Path, *parts: str) -> Path:
    """Join ``parts`` onto ``root`` and reject any escape from it."""
    candidate = (root / Path(*parts)).resolve()
    root_resolved = root.resolve()
    if root_resolved not in candidate.parents and candidate != root_resolved:
        raise StorageError("Resolved path escapes the configured data directory.")
    return candidate


class DataPaths:
    """Resolves the on-disk locations for a document's raw file and derived assets."""

    def __init__(self, data_dir: str) -> None:
        # Resolved eagerly so every path derived below (including the ones
        # returned by _resolve_within, which itself resolves) shares the
        # same absolute form — avoids relative_to() mismatches from
        # platform symlinks (e.g. macOS /tmp -> /private/tmp).
        self.root = Path(data_dir).resolve()
        self.raw_root = self.root / "raw"
        self.processed_root = self.root / "processed"

    def raw_dir(self, document_id: str) -> Path:
        return _resolve_within(self.raw_root, document_id)

    def raw_file_path(self, document_id: str, filename: str) -> Path:
        safe_name = sanitize_filename(filename)
        return _resolve_within(self.raw_root, document_id, safe_name)

    def images_dir(self, document_id: str) -> Path:
        return _resolve_within(self.processed_root, document_id, "images")

    def image_path(self, document_id: str, block_id: str, extension: str = "png") -> Path:
        safe_block_id = sanitize_filename(block_id)
        return _resolve_within(
            self.processed_root, document_id, "images", f"{safe_block_id}.{extension}"
        )

    def processed_dir(self, document_id: str) -> Path:
        return _resolve_within(self.processed_root, document_id)

    def resolve_stored_path(self, relative_path: str) -> Path:
        """Resolve a `storage_path` value (as stored on `Artifact`/`Chunk`,
        already relative to the data root) back to an absolute path,
        rejecting any attempt to escape the data root — same discipline as
        every other path helper on this class."""
        return _resolve_within(self.root, relative_path)


def save_upload(paths: DataPaths, document_id: str, filename: str, data: bytes) -> Path:
    """Persist raw uploaded bytes and return the path written."""
    target = paths.raw_file_path(document_id, filename)
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        target.write_bytes(data)
    except OSError as exc:
        raise StorageError("Failed to write uploaded file to storage.") from exc
    return target


def delete_document_files(paths: DataPaths, document_id: str) -> None:
    """Remove a document's raw upload and derived artifacts from disk.
    Best-effort: a missing directory (already cleaned up, or a document
    that only ever had rows without files) is not an error."""
    for directory in (paths.raw_dir(document_id), paths.processed_dir(document_id)):
        shutil.rmtree(directory, ignore_errors=True)


class ImageStorage(Protocol):
    """Collaborator used by parsers to persist extracted images."""

    def save(self, document_id: str, block_id: str, image: Image) -> str: ...


class FileImageStorage:
    """Saves extracted images under ``data/processed/<document_id>/images/``."""

    def __init__(self, paths: DataPaths) -> None:
        self._paths = paths

    def save(self, document_id: str, block_id: str, image: Image) -> str:
        target = self._paths.image_path(document_id, block_id)
        target.parent.mkdir(parents=True, exist_ok=True)
        try:
            image.convert("RGBA").save(target, format="PNG")
        except OSError as exc:
            raise StorageError("Failed to write extracted image to storage.") from exc
        # Store a path relative to the data root for portability across machines.
        return str(target.relative_to(self._paths.root))
