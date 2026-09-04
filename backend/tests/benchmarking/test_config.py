from pathlib import Path

from app.benchmarking.config import RunConfig

REPO_ROOT = Path(__file__).resolve().parents[3]


def test_load_baseline_config():
    config = RunConfig.load(REPO_ROOT / "evaluation" / "configs" / "baseline.yaml")
    assert config.name == "baseline"
    assert config.chunking_variant == "baseline"
    assert "A_bm25" in config.retrieval_configs
    assert 5 in config.top_k_values


def test_load_final_system_config():
    config = RunConfig.load(REPO_ROOT / "evaluation" / "configs" / "final_system.yaml")
    assert config.name == "final_system"
    assert (
        config.dataset_path
        == RunConfig.load(REPO_ROOT / "evaluation" / "configs" / "baseline.yaml").dataset_path
    )  # same dataset, per 7I "do not change the question set"


def test_config_defaults_seed_and_rrf_k(tmp_path):
    path = tmp_path / "minimal.yaml"
    path.write_text(
        """
name: minimal
dataset_path: evaluation/datasets/pilot_v1.json
embedding_model: BAAI/bge-small-en-v1.5
reranker_model: cross-encoder/ms-marco-MiniLM-L-6-v2
retrieval_configs: [A_bm25]
top_k_values: [5]
output_dir: evaluation/results
"""
    )
    config = RunConfig.load(path)
    assert config.seed == 42
    assert config.rrf_k == 60
