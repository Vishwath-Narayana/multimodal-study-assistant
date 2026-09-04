"""Reproducibility manifest for a benchmark run (Phase 7A.2)."""

from __future__ import annotations

import platform
import subprocess
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime

from app.benchmarking.availability import full_report
from app.benchmarking.schemas import BenchmarkDataset


def _git(*args: str) -> str:
    try:
        return subprocess.run(
            ["git", *args], capture_output=True, text=True, check=True, timeout=5
        ).stdout.strip()
    except Exception as exc:  # noqa: BLE001
        return f"UNKNOWN ({exc})"


@dataclass
class RunManifest:
    timestamp: str
    git_commit: str
    git_branch: str
    python_version: str
    platform: str
    dataset_id: str
    dataset_stats: dict
    seed: int
    availability: dict[str, dict] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


def build_manifest(dataset: BenchmarkDataset, seed: int = 42) -> RunManifest:
    availability = {
        name: {"available": c.available, "detail": c.detail} for name, c in full_report().items()
    }
    return RunManifest(
        timestamp=datetime.now(UTC).isoformat(),
        git_commit=_git("rev-parse", "HEAD"),
        git_branch=_git("rev-parse", "--abbrev-ref", "HEAD"),
        python_version=platform.python_version(),
        platform=platform.platform(),
        dataset_id=dataset.dataset_id,
        dataset_stats=dataset.stats(),
        seed=seed,
        availability=availability,
    )
