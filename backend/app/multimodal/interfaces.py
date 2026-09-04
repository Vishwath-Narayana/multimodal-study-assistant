"""Abstract interfaces for Phase 4 multimodal providers.

Mirrors `app.retrieval.interfaces`/`app.generation.interfaces`: orchestration
code (`app.multimodal.image_processing`, `audio_service`) depends only on
these ABCs, never on a concrete OCR/VLM/ASR SDK directly (ADR-004-style
separation, spec section 8/10/15: "must be replaceable, mockable,
optional, configuration-driven").
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from app.multimodal.models import OCRResult, TranscriptionResult, VisionDescription


class VisionProvider(ABC):
    """Produces a controlled, uncertainty-aware description of one image."""

    @abstractmethod
    def describe(self, image_path: Path, *, context: str = "") -> VisionDescription:
        """`context` is surrounding document text (section/heading), passed
        only to help the model use consistent terminology — never treated
        as ground truth about the image's content. Must not raise for a
        reachable-but-failing backend; return a `FAILED` result instead."""

    @abstractmethod
    def is_available(self) -> bool:
        """Cheap reachability/configuration check, never raises."""

    @property
    @abstractmethod
    def model_id(self) -> str: ...


class OCRProvider(ABC):
    """Extracts visible text from one image artifact."""

    @abstractmethod
    def extract(self, image_path: Path) -> OCRResult: ...

    @abstractmethod
    def is_available(self) -> bool: ...

    @property
    @abstractmethod
    def engine_id(self) -> str: ...


class TranscriptionProvider(ABC):
    """Timestamped speech-to-text transcription of one audio file."""

    @abstractmethod
    def transcribe(self, audio_path: Path, *, language: str | None = None) -> TranscriptionResult:
        ...

    @abstractmethod
    def is_available(self) -> bool: ...

    @property
    @abstractmethod
    def model_id(self) -> str: ...
