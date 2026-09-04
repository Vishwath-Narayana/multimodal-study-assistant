"""Deterministic test doubles for multimodal providers, so the default test
suite never needs a reachable Ollama server, tesseract binary, or a real
Whisper model download."""

from __future__ import annotations

from pathlib import Path

from app.ingestion.models import VisionStatus
from app.multimodal.interfaces import OCRProvider, TranscriptionProvider, VisionProvider
from app.multimodal.models import (
    OCRResult,
    TranscriptionResult,
    TranscriptionStatus,
    TranscriptSegment,
    VisionDescription,
)


class FakeVisionProvider(VisionProvider):
    def __init__(
        self,
        available: bool = True,
        description: str = "A labeled diagram showing three connected boxes.",
        fails: bool = False,
        model: str = "fake-vlm",
    ) -> None:
        self._available = available
        self._description = description
        self._fails = fails
        self._model = model

    @property
    def model_id(self) -> str:
        return self._model

    def is_available(self) -> bool:
        return self._available

    def describe(self, image_path: Path, *, context: str = "") -> VisionDescription:
        if not self._available:
            return VisionDescription(status=VisionStatus.UNAVAILABLE, model=self._model)
        if self._fails:
            return VisionDescription(status=VisionStatus.FAILED, model=self._model)
        return VisionDescription(
            status=VisionStatus.AVAILABLE, description=self._description, model=self._model
        )


class FakeOCRProvider(OCRProvider):
    def __init__(
        self, available: bool = True, text: str = "Figure 1: Pipeline", fails: bool = False
    ) -> None:
        self._available = available
        self._text = text
        self._fails = fails

    @property
    def engine_id(self) -> str:
        return "fake-ocr"

    def is_available(self) -> bool:
        return self._available

    def extract(self, image_path: Path) -> OCRResult:
        if not self._available:
            return OCRResult(status=VisionStatus.UNAVAILABLE, engine=self.engine_id)
        if self._fails:
            return OCRResult(status=VisionStatus.FAILED, engine=self.engine_id)
        return OCRResult(status=VisionStatus.AVAILABLE, text=self._text, engine=self.engine_id)


class FakeTranscriptionProvider(TranscriptionProvider):
    def __init__(
        self,
        available: bool = True,
        segments: list[TranscriptSegment] | None = None,
        fails: bool = False,
        model: str = "fake-whisper",
        language: str = "en",
    ) -> None:
        self._available = available
        self._segments = segments if segments is not None else [
            TranscriptSegment(text="Welcome to lecture one.", start=0.0, end=2.5),
            TranscriptSegment(text="Today we cover photosynthesis.", start=2.5, end=5.0),
        ]
        self._fails = fails
        self._model = model
        self._language = language

    @property
    def model_id(self) -> str:
        return self._model

    def is_available(self) -> bool:
        return self._available

    def transcribe(self, audio_path: Path, *, language: str | None = None) -> TranscriptionResult:
        if not self._available:
            return TranscriptionResult(status=TranscriptionStatus.UNAVAILABLE, model=self._model)
        if self._fails:
            return TranscriptionResult(status=TranscriptionStatus.FAILED, model=self._model)
        return TranscriptionResult(
            status=TranscriptionStatus.AVAILABLE,
            segments=list(self._segments),
            model=self._model,
            language=self._language,
        )
