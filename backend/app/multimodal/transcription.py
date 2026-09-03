"""`TranscriptionProvider` implementations.

`WhisperTranscriptionProvider` wraps `faster-whisper` (CTranslate2-based,
no torch dependency, CPU-compatible — see pyproject.toml). Model
size/device/compute type are configuration-driven
(`Settings.whisper_model`/`whisper_device`/`whisper_compute_type`, spec
section 15), never hard-coded. The model is loaded once and reused across
calls, same lifecycle discipline as `BGEEmbeddingProvider`/
`CrossEncoderReranker`.

`NullTranscriptionProvider` is the default when `Settings.
transcription_provider` is empty — always unavailable, never fabricates a
transcript (spec: "no fake transcript is created").
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from app.multimodal.interfaces import TranscriptionProvider
from app.multimodal.models import TranscriptionResult, TranscriptionStatus, TranscriptSegment

if TYPE_CHECKING:
    from faster_whisper import WhisperModel


class NullTranscriptionProvider(TranscriptionProvider):
    def transcribe(self, audio_path: Path, *, language: str | None = None) -> TranscriptionResult:
        return TranscriptionResult(status=TranscriptionStatus.UNAVAILABLE)

    def is_available(self) -> bool:
        return False

    @property
    def model_id(self) -> str:
        return ""


class WhisperTranscriptionProvider(TranscriptionProvider):
    def __init__(
        self,
        model_size: str = "base",
        device: str = "auto",
        compute_type: str = "int8",
    ) -> None:
        self._model_size = model_size
        self._device = device
        self._compute_type = compute_type
        self._model: WhisperModel | None = None
        self._load_failed = False

    @property
    def model_id(self) -> str:
        return f"whisper-{self._model_size}"

    def _ensure_loaded(self) -> bool:
        if self._model is not None:
            return True
        if self._load_failed:
            return False
        try:
            from faster_whisper import WhisperModel

            self._model = WhisperModel(
                self._model_size, device=self._device, compute_type=self._compute_type
            )
            return True
        except Exception:  # noqa: BLE001 - model download/load failure
            self._load_failed = True
            return False

    def is_available(self) -> bool:
        return self._ensure_loaded()

    def transcribe(self, audio_path: Path, *, language: str | None = None) -> TranscriptionResult:
        if not self._ensure_loaded():
            return TranscriptionResult(status=TranscriptionStatus.UNAVAILABLE, model=self.model_id)
        assert self._model is not None
        try:
            segments_iter, info = self._model.transcribe(str(audio_path), language=language or None)
            segments = [
                TranscriptSegment(text=seg.text.strip(), start=float(seg.start), end=float(seg.end))
                for seg in segments_iter
            ]
        except Exception:  # noqa: BLE001 - engine loaded but failed on this file
            return TranscriptionResult(status=TranscriptionStatus.FAILED, model=self.model_id)

        return TranscriptionResult(
            status=TranscriptionStatus.AVAILABLE,
            segments=segments,
            model=self.model_id,
            language=getattr(info, "language", None),
        )
