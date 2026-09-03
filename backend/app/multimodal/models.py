"""Phase 4 multimodal domain model.

Follows the same discipline as `app.retrieval.models`/`app.generation.models`:
plain dataclasses, independent of any specific OCR/VLM/ASR library. The
`VisionStatus` enum shared with `app.ingestion.models` is reused directly
rather than duplicated (OCR reuses it too — see that module's docstring).

`Artifact` is the provenance record for one original visual/audio artifact
(spec section 5/7/24): it never carries the artifact's bytes, only a
storage path plus enough metadata to reconstruct "where did this come
from" — the actual file lives under `data/raw` or `data/processed` (see
`app.ingestion.storage`), never in SQLite.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from app.ingestion.models import VisionStatus

__all__ = [
    "Artifact",
    "ArtifactType",
    "OCRResult",
    "TranscriptSegment",
    "TranscriptionResult",
    "TranscriptionStatus",
    "VisionDescription",
    "VisionStatus",
]


class ArtifactType(StrEnum):
    IMAGE = "image"
    AUDIO = "audio"


@dataclass
class Artifact:
    """Provenance record for one original image/audio artifact.

    `chunk_id` is `None` until the enclosing chunk's id is known (chunking
    happens after image enrichment — see `app.multimodal.image_processing`)
    and is backfilled via `app.multimodal.repository.ArtifactRepository.
    set_chunk_id` once it is. No artifact is left permanently unlinked by
    the time ingestion completes (spec section 5: "do not create orphaned
    visual/audio chunks").
    """

    id: str
    document_id: str
    artifact_type: ArtifactType
    storage_path: str
    mime_type: str | None = None
    sha256: str | None = None
    chunk_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: str = ""


@dataclass
class OCRResult:
    """One OCR attempt over one image artifact.

    `status` follows the same "never fabricate" discipline as
    `VisionDescription` below — `UNAVAILABLE` (no OCR engine configured/
    reachable) and `FAILED` (engine ran but errored) are kept distinct from
    a successful empty-text result (an image with no legible text is a
    valid `AVAILABLE` result with `text == ""`, not a failure).
    """

    status: VisionStatus
    text: str | None = None
    engine: str | None = None


@dataclass
class VisionDescription:
    """One VLM description attempt over one image/diagram artifact.

    Spec section 8: "Never claim a VLM description exists when it was not
    generated" — `status` is always set explicitly by the provider, never
    inferred from whether `description` happens to be non-empty.
    """

    status: VisionStatus
    description: str | None = None
    model: str | None = None


class TranscriptionStatus(StrEnum):
    """Mirrors `VisionStatus`'s three-way "did this actually run" split,
    kept as its own enum (rather than reusing `VisionStatus`) since audio
    transcription is a structurally different pipeline stage (spec section
    15: "Never fabricate transcription results")."""

    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"
    FAILED = "failed"


@dataclass
class TranscriptSegment:
    """One Whisper-style timestamped segment, before chunk grouping."""

    text: str
    start: float
    end: float


@dataclass
class TranscriptionResult:
    status: TranscriptionStatus
    segments: list[TranscriptSegment] = field(default_factory=list)
    model: str | None = None
    language: str | None = None
