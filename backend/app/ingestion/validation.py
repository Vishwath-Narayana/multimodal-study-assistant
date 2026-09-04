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

# Magic-byte signatures for formats that have one (spec section 8B: "never
# trust ... file extension alone"). DOCX/PPTX are both ZIP containers, so
# they share the ZIP local-file-header signature; PDF has its own. HTML has
# no reliable binary signature (it is arbitrary text/markup) — it is
# deliberately left out of `_MAGIC_BYTES` rather than guessed at, and
# `_looks_like_declared_type` treats "no known signature" as "cannot check,
# don't false-reject" (same policy as `app.multimodal.security`).
_MAGIC_BYTES: dict[str, tuple[bytes, ...]] = {
    "pdf": (b"%PDF-",),
    "docx": (b"PK\x03\x04",),
    "pptx": (b"PK\x03\x04",),
}


def _looks_like_declared_type(data: bytes, extension: str) -> bool:
    signatures = _MAGIC_BYTES.get(extension)
    if signatures is None:
        return True
    return any(data.startswith(sig) for sig in signatures)


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

    if not _looks_like_declared_type(data, extension):
        raise ValidationError(
            f"The uploaded file does not look like a valid .{extension} file."
        )

    return ValidatedUpload(
        original_filename=filename,
        safe_filename=safe_filename,
        file_type=extension,
        size_bytes=len(data),
    )
