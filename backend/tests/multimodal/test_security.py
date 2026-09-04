from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image

from app.multimodal.errors import ArtifactValidationError, AudioValidationError
from app.multimodal.security import validate_audio_upload, validate_image_artifact

_EXTENSIONS = ("wav", "mp3", "m4a")


def test_validate_audio_upload_accepts_valid_wav(wav_bytes: bytes) -> None:
    result = validate_audio_upload(
        "lecture.wav", wav_bytes, supported_extensions=_EXTENSIONS, max_size_bytes=10_000_000
    )
    assert result.file_type == "wav"
    assert result.size_bytes == len(wav_bytes)


def test_validate_audio_upload_rejects_unsupported_extension(wav_bytes: bytes) -> None:
    with pytest.raises(AudioValidationError, match="Unsupported"):
        validate_audio_upload(
            "lecture.ogg", wav_bytes, supported_extensions=_EXTENSIONS, max_size_bytes=10_000_000
        )


def test_validate_audio_upload_rejects_empty_file() -> None:
    with pytest.raises(AudioValidationError, match="empty"):
        validate_audio_upload(
            "lecture.wav", b"", supported_extensions=_EXTENSIONS, max_size_bytes=10_000_000
        )


def test_validate_audio_upload_rejects_oversized_file(wav_bytes: bytes) -> None:
    with pytest.raises(AudioValidationError, match="exceeds"):
        validate_audio_upload(
            "lecture.wav", wav_bytes, supported_extensions=_EXTENSIONS, max_size_bytes=1
        )


def test_validate_audio_upload_rejects_mismatched_magic_bytes() -> None:
    with pytest.raises(AudioValidationError, match="does not look like"):
        validate_audio_upload(
            "lecture.wav",
            b"not actually a wav file, just plain bytes",
            supported_extensions=_EXTENSIONS,
            max_size_bytes=10_000_000,
        )


def test_validate_audio_upload_requires_filename(wav_bytes: bytes) -> None:
    with pytest.raises(AudioValidationError, match="filename"):
        validate_audio_upload(
            "", wav_bytes, supported_extensions=_EXTENSIONS, max_size_bytes=10_000_000
        )


def test_validate_image_artifact_accepts_valid_small_image(tmp_path: Path) -> None:
    path = tmp_path / "img.png"
    Image.new("RGB", (10, 10), color="red").save(path, format="PNG")
    validate_image_artifact(path, max_size_bytes=10_000_000, max_pixels=1_000_000)


def test_validate_image_artifact_rejects_oversized_file(tmp_path: Path) -> None:
    path = tmp_path / "img.png"
    Image.new("RGB", (10, 10), color="red").save(path, format="PNG")
    with pytest.raises(ArtifactValidationError, match="exceeds"):
        validate_image_artifact(path, max_size_bytes=1, max_pixels=1_000_000)


def test_validate_image_artifact_rejects_decompression_bomb(tmp_path: Path) -> None:
    path = tmp_path / "img.png"
    # A pixel count Pillow itself would refuse when MAX_IMAGE_PIXELS is set low.
    Image.new("RGB", (2000, 2000), color="blue").save(path, format="PNG")
    with pytest.raises(ArtifactValidationError, match="failed validation"):
        validate_image_artifact(path, max_size_bytes=10_000_000, max_pixels=1000)


def test_validate_image_artifact_rejects_corrupt_file(tmp_path: Path) -> None:
    path = tmp_path / "img.png"
    path.write_bytes(b"not a real png")
    with pytest.raises(ArtifactValidationError, match="failed validation"):
        validate_image_artifact(path, max_size_bytes=10_000_000, max_pixels=1_000_000)


def test_validate_image_artifact_missing_file_raises(tmp_path: Path) -> None:
    with pytest.raises(ArtifactValidationError):
        validate_image_artifact(
            tmp_path / "missing.png", max_size_bytes=10_000_000, max_pixels=1_000_000
        )
