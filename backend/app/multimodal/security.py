"""Multimodal input validation.

Extracted multimodal content is untrusted the same way an uploaded document
is (see docs/research/security.md): images can be decompression bombs or
malformed; audio can be oversized or malformed; OCR text and VLM
descriptions are *data*, never instructions (enforced downstream — see
`app.generation.prompts` — not by this module). This module only validates
shape/size before any processing is attempted; it does not interpret
content.

Reuses `app.ingestion.storage.sanitize_filename` rather than duplicating
filename-safety logic, and follows the same "raise a safe, user-facing
error" discipline as `app.ingestion.validation`.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from PIL import Image

from app.ingestion.storage import sanitize_filename
from app.multimodal.errors import ArtifactValidationError, AudioValidationError

# WAV/RIFF, MP3 (ID3 tag or a raw MPEG frame sync), and M4A/MP4 (ftyp box at
# offset 4) magic-byte prefixes — a cheap, dependency-free sanity check that
# the bytes at least resemble the claimed format before anything is written
# to disk or handed to a transcription model. Not a full format validator.
_AUDIO_MAGIC_BYTES: dict[str, tuple[bytes, ...]] = {
    "wav": (b"RIFF",),
    "mp3": (b"ID3", b"\xff\xfb", b"\xff\xf3", b"\xff\xf2"),
    "m4a": (b"ftyp",),  # checked at offset 4, see _looks_like_audio
}


@dataclass(frozen=True)
class ValidatedAudioUpload:
    original_filename: str
    safe_filename: str
    file_type: str
    size_bytes: int


def validate_audio_upload(
    filename: str,
    data: bytes,
    *,
    supported_extensions: tuple[str, ...],
    max_size_bytes: int,
) -> ValidatedAudioUpload:
    """Validate an in-memory audio upload. Mirrors
    `app.ingestion.validation.validate_upload`'s shape/size checks; audio
    gets its own function (rather than a shared one) because the magic-byte
    sniff below has no document-upload equivalent."""
    if not filename or not filename.strip():
        raise AudioValidationError("A filename is required.")

    safe_filename = sanitize_filename(filename)
    extension = safe_filename.rsplit(".", 1)[-1].lower() if "." in safe_filename else ""

    if extension not in supported_extensions:
        supported = ", ".join(sorted(supported_extensions))
        raise AudioValidationError(
            f"Unsupported audio type '.{extension}'. Supported types: {supported}."
        )

    if not data:
        raise AudioValidationError("The uploaded audio file is empty.")

    if len(data) > max_size_bytes:
        max_mb = max_size_bytes / (1024 * 1024)
        raise AudioValidationError(
            f"The uploaded audio file exceeds the {max_mb:.0f}MB size limit."
        )

    if not _looks_like_audio(data, extension):
        raise AudioValidationError(
            f"The uploaded file does not look like a valid .{extension} audio file."
        )

    return ValidatedAudioUpload(
        original_filename=filename,
        safe_filename=safe_filename,
        file_type=extension,
        size_bytes=len(data),
    )


def _looks_like_audio(data: bytes, extension: str) -> bool:
    prefixes = _AUDIO_MAGIC_BYTES.get(extension)
    if prefixes is None:
        return True  # no known signature to check against; don't false-reject
    if extension == "m4a":
        return data[4:8] == b"ftyp"
    return any(data.startswith(p) for p in prefixes)


def validate_image_artifact(
    path: Path, *, max_size_bytes: int, max_pixels: int
) -> None:
    """Guard against oversized files and decompression bombs before an
    already-extracted image is handed to OCR/VLM processing.

    `Image.MAX_IMAGE_PIXELS` is Pillow's own global decompression-bomb
    guard (it raises `Image.DecompressionBombError` above the threshold);
    this function additionally checks the file size up front, and reports
    both failure modes as `ArtifactValidationError` so callers get one
    consistent exception type regardless of which check fails.
    """
    try:
        size_bytes = path.stat().st_size
    except OSError as exc:
        raise ArtifactValidationError(f"Could not read image artifact: {path.name}.") from exc

    if size_bytes > max_size_bytes:
        max_mb = max_size_bytes / (1024 * 1024)
        raise ArtifactValidationError(
            f"Image artifact '{path.name}' exceeds the {max_mb:.0f}MB size limit."
        )

    original_limit = Image.MAX_IMAGE_PIXELS
    try:
        Image.MAX_IMAGE_PIXELS = max_pixels
        with Image.open(path) as img:
            img.verify()
    except Exception as exc:  # noqa: BLE001 - any Pillow failure means "not a safe image"
        raise ArtifactValidationError(
            f"Image artifact '{path.name}' failed validation (corrupt, oversized, or unsupported)."
        ) from exc
    finally:
        Image.MAX_IMAGE_PIXELS = original_limit
