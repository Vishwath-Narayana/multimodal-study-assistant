from __future__ import annotations

from pathlib import Path

import pytest

from app.retrieval.errors import (
    CorruptedManifestError,
    IndexNotBuiltError,
    NoIndexedChunksError,
    StaleIndexError,
)
from app.retrieval.faiss_index import FaissIndexStore
from tests.retrieval.conftest import make_chunk
from tests.retrieval.fakes import FakeEmbeddingProvider

CORPUS = [
    make_chunk("c1", "Photosynthesis converts light energy into chemical energy."),
    make_chunk("c2", "Cellular respiration releases energy stored in glucose."),
    make_chunk("c3", "The mitochondria is the powerhouse of the cell."),
]


def _build(tmp_path: Path, chunks=None) -> FaissIndexStore:
    return FaissIndexStore.build(
        CORPUS if chunks is None else chunks,
        FakeEmbeddingProvider(),
        tmp_path / "indexes",
        chunk_target_tokens=512,
        chunk_overlap_tokens=50,
    )


def test_build_creates_index_manifest_and_id_map_files(tmp_path: Path) -> None:
    _build(tmp_path)
    index_dir = tmp_path / "indexes"
    assert (index_dir / "faiss.index").exists()
    assert (index_dir / "manifest.json").exists()
    assert (index_dir / "id_map.json").exists()


def test_manifest_records_expected_fields(tmp_path: Path) -> None:
    store = _build(tmp_path)
    manifest = store.manifest
    assert manifest.embedding_model == "fake-embedding-provider"
    assert manifest.chunk_count == len(CORPUS)
    assert manifest.index_type == "IndexFlatIP"
    assert set(manifest.chunk_fingerprints) == {c.id for c in CORPUS}


def test_search_returns_nearest_neighbor_for_identical_text(tmp_path: Path) -> None:
    store = _build(tmp_path)
    provider = FakeEmbeddingProvider()
    query_vector = provider.embed_query(CORPUS[0].content)
    hits = store.search(query_vector, top_k=3)
    assert hits[0][0] == "c1"


def test_top_k_is_respected(tmp_path: Path) -> None:
    store = _build(tmp_path)
    provider = FakeEmbeddingProvider()
    hits = store.search(provider.embed_query("energy"), top_k=1)
    assert len(hits) == 1


def test_top_k_larger_than_corpus_is_clamped(tmp_path: Path) -> None:
    store = _build(tmp_path)
    provider = FakeEmbeddingProvider()
    hits = store.search(provider.embed_query("energy"), top_k=1000)
    assert len(hits) == len(CORPUS)


def test_load_from_disk_reproduces_search_results(tmp_path: Path) -> None:
    _build(tmp_path)
    reloaded = FaissIndexStore(index_dir=tmp_path / "indexes").load()
    provider = FakeEmbeddingProvider()
    hits = reloaded.search(provider.embed_query(CORPUS[1].content), top_k=1)
    assert hits[0][0] == "c2"


def test_missing_index_raises(tmp_path: Path) -> None:
    with pytest.raises(IndexNotBuiltError):
        FaissIndexStore(index_dir=tmp_path / "missing").load()


def test_empty_corpus_raises(tmp_path: Path) -> None:
    with pytest.raises(NoIndexedChunksError):
        _build(tmp_path, chunks=[])


def test_duplicate_chunk_ids_are_indexed_once(tmp_path: Path) -> None:
    dup = make_chunk("c1", "A duplicate id, different content.")
    store = _build(tmp_path, chunks=[*CORPUS, dup])
    assert store.manifest.chunk_count == len(CORPUS)


def test_stale_detection_when_chunk_content_changes(tmp_path: Path) -> None:
    store = _build(tmp_path)
    changed = [make_chunk("c1", "Totally different content now."), *CORPUS[1:]]
    assert store.is_stale(changed) is True
    with pytest.raises(StaleIndexError):
        store.raise_if_stale(changed)


def test_not_stale_when_chunks_are_unchanged(tmp_path: Path) -> None:
    store = _build(tmp_path)
    assert store.is_stale(CORPUS) is False
    store.raise_if_stale(CORPUS)  # should not raise


def test_stale_detection_when_chunk_added(tmp_path: Path) -> None:
    store = _build(tmp_path)
    more = [*CORPUS, make_chunk("c4", "A brand new chunk.")]
    assert store.is_stale(more) is True


def test_rebuild_overwrites_previous_index(tmp_path: Path) -> None:
    _build(tmp_path)
    rebuilt = _build(tmp_path, chunks=CORPUS[:2])
    assert rebuilt.manifest.chunk_count == 2
    reloaded = FaissIndexStore(index_dir=tmp_path / "indexes").load()
    assert reloaded.manifest.chunk_count == 2


def test_corrupted_manifest_raises(tmp_path: Path) -> None:
    store = _build(tmp_path)
    (store.index_dir / "manifest.json").write_text("{not valid json")
    with pytest.raises(CorruptedManifestError):
        FaissIndexStore(index_dir=tmp_path / "indexes").load()
