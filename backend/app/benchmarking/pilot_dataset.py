"""Loader for evaluation/datasets/pilot_v1.json (see
scripts/build_phase7_pilot_dataset.py, which generates it)."""

from __future__ import annotations

import json
from pathlib import Path

from app.benchmarking.schemas import BenchmarkDataset, BenchmarkQuestion

DEFAULT_PATH = Path(__file__).resolve().parents[3] / "evaluation" / "datasets" / "pilot_v1.json"


def load_pilot_dataset(path: Path | None = None) -> BenchmarkDataset:
    path = path or DEFAULT_PATH
    data = json.loads(path.read_text())
    return BenchmarkDataset(
        dataset_id=data["dataset_id"],
        description=data["description"],
        documents=data["documents"],
        questions=[BenchmarkQuestion.from_dict(q) for q in data["questions"]],
        limitations=list(data.get("limitations", [])),
    )
