from app.benchmarking.manifest import build_manifest
from app.benchmarking.schemas import BenchmarkDataset


def test_build_manifest_captures_required_reproducibility_fields():
    dataset = BenchmarkDataset(dataset_id="d1", description="test", documents={}, questions=[])
    manifest = build_manifest(dataset, seed=7)
    assert manifest.seed == 7
    assert manifest.dataset_id == "d1"
    assert manifest.timestamp  # non-empty ISO string
    assert manifest.git_commit  # never silently empty — UNKNOWN(...) on failure
    assert "sentence_transformers" in manifest.availability
    assert "ollama" in manifest.availability


def test_manifest_to_dict_is_json_serializable():
    import json

    dataset = BenchmarkDataset(dataset_id="d1", description="test", documents={}, questions=[])
    manifest = build_manifest(dataset)
    json.dumps(manifest.to_dict())  # must not raise
