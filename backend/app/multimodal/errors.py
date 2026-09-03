"""Multimodal-specific exceptions.

Mirrors `app.ingestion.errors`/`app.retrieval.errors`: a base class plus
specific subclasses, each carrying a safe, user-facing `message`.
"""

from __future__ import annotations


class MultimodalError(Exception):
    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class ArtifactValidationError(MultimodalError):
    """A visual/audio artifact failed validation (size, dimensions, format)."""


class AudioValidationError(MultimodalError):
    """An uploaded audio file failed validation before transcription."""


class TranscriptionUnavailableError(MultimodalError):
    """A transcription was required but no transcription provider is configured/reachable."""


class TranscriptionFailedError(MultimodalError):
    """The transcription provider was reachable but transcription itself failed."""
