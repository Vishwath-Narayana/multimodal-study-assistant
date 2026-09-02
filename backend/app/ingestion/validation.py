"""Upload validation.

Runs before any parsing is attempted. Uploaded content is untrusted data
(see docs/research/security.md): we validate shape and size here, but
never execute it, and never trust the filename alone for document identity
(that is what content hashing in :mod:`app.ingestion.hashing` is for).
"""

from __future__ import annotations

from dataclasses import dataclass

from app.ingestion.errors import ValidationError
from app.ingestion.storage import sanitize_filename


@dataclass(frozen=True)
class ValidatedUpload:
    original_filename: str
    safe_filename: str
    file_type: str
    size_bytes: int


def validate_upload(
    filename: str,
    data: bytes,
    *,
    supported_extensions: tuple[str, ...],
    max_size_bytes: int,
) -> ValidatedUpload:
    """Validate an in-memory upload and return its normalized identity.

    Raises :class:`ValidationError` with a safe, user-facing message on any
    failure. Does not attempt to parse the file's content.
    """
    if not filename or not filename.strip():
        raise ValidationError("A filename is required.")

    safe_filename = sanitize_filename(filename)
    extension = safe_filename.rsplit(".", 1)[-1].lower() if "." in safe_filename else ""

    if extension not in supported_extensions:
        supported = ", ".join(sorted(supported_extensions))
        raise ValidationError(
            f"Unsupported file type '.{extension}'. Supported types: {supported}."
        )

    if data is None or len(data) == 0:
        raise ValidationError("The uploaded file is empty.")

    if len(data) > max_size_bytes:
        max_mb = max_size_bytes / (1024 * 1024)
        raise ValidationError(f"The uploaded file exceeds the {max_mb:.0f}MB size limit.")

    return ValidatedUpload(
        original_filename=filename,
        safe_filename=safe_filename,
        file_type=extension,
        size_bytes=len(data),
    )
