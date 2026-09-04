"""Security: path traversal protection and safe filename handling."""

from pathlib import Path

import pytest

from app.ingestion.errors import StorageError
from app.ingestion.storage import DataPaths, sanitize_filename, save_upload


def test_sanitize_filename_strips_path_components() -> None:
    # Path(...).name collapses any directory components to the basename,
    # so a traversal attempt just becomes the trailing filename.
    assert sanitize_filename("../../etc/passwd") == "passwd"


def test_sanitize_filename_removes_unsafe_characters() -> None:
    assert sanitize_filename("my notes!@#$.pdf") == "my_notes_.pdf"


def test_sanitize_filename_never_empty() -> None:
    assert sanitize_filename("...") != ""


def test_raw_file_path_stays_within_data_root(tmp_path: Path) -> None:
    paths = DataPaths(str(tmp_path))
    resolved = paths.raw_file_path("doc123", "notes.pdf")
    assert str(resolved).startswith(str(tmp_path.resolve()))


def test_raw_file_path_rejects_traversal_in_document_id(tmp_path: Path) -> None:
    paths = DataPaths(str(tmp_path))
    with pytest.raises(StorageError):
        paths.raw_dir("../../outside")


def test_save_upload_writes_bytes(tmp_path: Path) -> None:
    paths = DataPaths(str(tmp_path))
    written = save_upload(paths, "doc123", "notes.pdf", b"hello world")
    assert written.read_bytes() == b"hello world"
    assert written.parent == paths.raw_dir("doc123")
