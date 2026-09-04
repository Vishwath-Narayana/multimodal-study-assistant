"""Versioned run configuration (Phase 7A.1) — loaded from YAML, never
hard-coded in the runner."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

DEFAULT_CONFIG_DIR = Path(__file__).resolve().parents[3] / "evaluation" / "configs"


@dataclass
class RunConfig:
    name: str
    dataset_path: str
    embedding_model: str
    reranker_model: str
    retrieval_configs: list[str]
    top_k_values: list[int]
    rrf_k: int
    seed: int
    output_dir: str
    chunking_variant: str = "baseline"  # "baseline" | "bge_aware"

    @staticmethod
    def load(path: Path) -> RunConfig:
        data = yaml.safe_load(path.read_text())
        return RunConfig(
            name=data["name"],
            dataset_path=data["dataset_path"],
            embedding_model=data["embedding_model"],
            reranker_model=data["reranker_model"],
            retrieval_configs=list(data["retrieval_configs"]),
            top_k_values=list(data["top_k_values"]),
            rrf_k=int(data.get("rrf_k", 60)),
            seed=int(data.get("seed", 42)),
            output_dir=data["output_dir"],
            chunking_variant=data.get("chunking_variant", "baseline"),
        )
