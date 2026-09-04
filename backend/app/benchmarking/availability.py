"""Actual dependency/model availability checks.

Phase 7's absolute rule is "no fabricated results": every evaluation run
must record what was actually available, not assumed. Every function here
does a real, cheap check (no network calls beyond what's already cached
locally) and returns a plain boolean plus a human-readable detail string —
never raises, so a manifest can always be built even when everything is
unavailable.
"""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass


@dataclass
class AvailabilityCheck:
    name: str
    available: bool
    detail: str


def check_ollama() -> AvailabilityCheck:
    """Ollama backs generation, HyDE, and the VLM in this project."""
    binary = shutil.which("ollama")
    if binary is None:
        return AvailabilityCheck("ollama", False, "`ollama` binary not found on PATH")
    try:
        result = subprocess.run(
            ["ollama", "list"], capture_output=True, text=True, timeout=5, check=False
        )
    except (subprocess.TimeoutExpired, OSError) as exc:
        return AvailabilityCheck("ollama", False, f"`ollama list` failed: {exc}")
    if result.returncode != 0:
        return AvailabilityCheck("ollama", False, f"`ollama list` exited {result.returncode}")
    return AvailabilityCheck("ollama", True, result.stdout.strip() or "ollama daemon reachable")


def check_tesseract() -> AvailabilityCheck:
    binary = shutil.which("tesseract")
    if binary is None:
        return AvailabilityCheck("tesseract", False, "`tesseract` binary not found on PATH")
    return AvailabilityCheck("tesseract", True, binary)


def check_faster_whisper() -> AvailabilityCheck:
    try:
        import faster_whisper  # noqa: F401
    except ImportError as exc:
        return AvailabilityCheck("faster_whisper", False, f"import failed: {exc}")
    return AvailabilityCheck("faster_whisper", True, "importable")


def check_sentence_transformers() -> AvailabilityCheck:
    try:
        import sentence_transformers  # noqa: F401
    except ImportError as exc:
        return AvailabilityCheck("sentence_transformers", False, f"import failed: {exc}")
    return AvailabilityCheck("sentence_transformers", True, sentence_transformers.__version__)


def check_faiss() -> AvailabilityCheck:
    try:
        import faiss  # noqa: F401
    except ImportError as exc:
        return AvailabilityCheck("faiss", False, f"import failed: {exc}")
    return AvailabilityCheck("faiss", True, "importable")


def full_report() -> dict[str, AvailabilityCheck]:
    checks = [
        check_sentence_transformers(),
        check_faiss(),
        check_ollama(),
        check_tesseract(),
        check_faster_whisper(),
    ]
    return {c.name: c for c in checks}
