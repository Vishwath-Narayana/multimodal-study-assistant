"""E, F: unsupported-extension and empty-file rejection, plus general validation rules."""

import pytest

from app.ingestion.errors import ValidationError
from app.ingestion.validation import validate_upload

SUPPORTED = ("pdf", "docx", "pptx", "html", "htm")
MAX_SIZE = 1024 * 1024
# %PDF- is the real PDF magic-byte signature (app.ingestion.validation now
# checks it — spec section 8B: "never trust ... file extension alone").
# HTML has no binary signature to check, so plain text is fine for it.
PDF_BYTES = b"%PDF-1.4\ncontent"


def test_accepts_a_supported_extension() -> None:
    result = validate_upload(
        "notes.pdf", PDF_BYTES, supported_extensions=SUPPORTED, max_size_bytes=MAX_SIZE
    )
    assert result.file_type == "pdf"
    assert result.size_bytes == len(PDF_BYTES)


def test_rejects_unsupported_extension() -> None:
    with pytest.raises(ValidationError, match="Unsupported file type"):
        validate_upload(
            "malware.exe", b"content", supported_extensions=SUPPORTED, max_size_bytes=MAX_SIZE
        )


def test_rejects_empty_file() -> None:
    with pytest.raises(ValidationError, match="empty"):
        validate_upload(
            "notes.pdf", b"", supported_extensions=SUPPORTED, max_size_bytes=MAX_SIZE
        )


def test_rejects_oversized_file() -> None:
    with pytest.raises(ValidationError, match="size limit"):
        validate_upload(
            "notes.pdf",
            b"x" * (MAX_SIZE + 1),
            supported_extensions=SUPPORTED,
            max_size_bytes=MAX_SIZE,
        )


def test_rejects_missing_filename() -> None:
    with pytest.raises(ValidationError):
        validate_upload("", b"content", supported_extensions=SUPPORTED, max_size_bytes=MAX_SIZE)


def test_sanitizes_path_traversal_in_filename() -> None:
    result = validate_upload(
        "../../etc/passwd.pdf", PDF_BYTES, supported_extensions=SUPPORTED, max_size_bytes=MAX_SIZE
    )
    assert "/" not in result.safe_filename
    assert ".." not in result.safe_filename


def test_rejects_content_that_does_not_match_the_declared_extension() -> None:
    """Spec section 8B: extension alone is never trusted — a file claiming
    to be a PDF but containing arbitrary bytes is rejected before parsing."""
    with pytest.raises(ValidationError, match="does not look like"):
        validate_upload(
            "notes.pdf",
            b"this is not a pdf file at all",
            supported_extensions=SUPPORTED,
            max_size_bytes=MAX_SIZE,
        )


def test_accepts_zip_based_docx_signature() -> None:
    result = validate_upload(
        "slides.docx",
        b"PK\x03\x04" + b"\x00" * 16,
        supported_extensions=SUPPORTED,
        max_size_bytes=MAX_SIZE,
    )
    assert result.file_type == "docx"
