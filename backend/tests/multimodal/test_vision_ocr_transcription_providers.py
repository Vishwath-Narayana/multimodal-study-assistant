"""NullVisionProvider/NullOCRProvider/NullTranscriptionProvider (the default,
config-off providers) plus the real providers' offline reachability checks
— exercised without requiring Ollama/tesseract/a downloaded Whisper model.
"""

from __future__ import annotations

from pathlib import Path

from app.ingestion.models import VisionStatus
from app.multimodal.models import TranscriptionStatus
from app.multimodal.ocr import NullOCRProvider, TesseractOCRProvider
from app.multimodal.transcription import NullTranscriptionProvider, WhisperTranscriptionProvider
from app.multimodal.vision import NullVisionProvider, OllamaVisionProvider


def test_null_vision_provider_always_unavailable(tmp_path: Path) -> None:
    provider = NullVisionProvider()
    assert provider.is_available() is False
    result = provider.describe(tmp_path / "img.png")
    assert result.status == VisionStatus.UNAVAILABLE
    assert result.description is None


def test_null_ocr_provider_always_unavailable(tmp_path: Path) -> None:
    provider = NullOCRProvider()
    assert provider.is_available() is False
    result = provider.extract(tmp_path / "img.png")
    assert result.status == VisionStatus.UNAVAILABLE
    assert result.text is None


def test_null_transcription_provider_always_unavailable(tmp_path: Path) -> None:
    provider = NullTranscriptionProvider()
    assert provider.is_available() is False
    result = provider.transcribe(tmp_path / "audio.wav")
    assert result.status == TranscriptionStatus.UNAVAILABLE
    assert result.segments == []


def test_ollama_vision_provider_unreachable_reports_unavailable() -> None:
    # No server on this port in the test environment — must return False,
    # not raise.
    provider = OllamaVisionProvider("http://localhost:1", "llava-phi3")
    assert provider.is_available() is False


def test_ollama_vision_provider_describe_on_missing_file_reports_failed(tmp_path: Path) -> None:
    provider = OllamaVisionProvider("http://localhost:1", "llava-phi3")
    result = provider.describe(tmp_path / "missing.png")
    assert result.status == VisionStatus.FAILED


def test_tesseract_ocr_provider_engine_id() -> None:
    assert TesseractOCRProvider().engine_id == "tesseract"


def test_tesseract_ocr_provider_is_available_never_raises() -> None:
    # Whether tesseract happens to be installed in this environment or not,
    # is_available() must return a bool, never raise.
    assert isinstance(TesseractOCRProvider().is_available(), bool)


def test_whisper_provider_model_id_before_load() -> None:
    provider = WhisperTranscriptionProvider(model_size="base")
    assert provider.model_id == "whisper-base"
