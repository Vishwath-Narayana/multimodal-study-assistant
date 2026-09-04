from __future__ import annotations

import numpy as np

from tests.retrieval.fakes import FAKE_DIMENSION, FakeEmbeddingProvider


def test_embed_documents_returns_expected_shape() -> None:
    provider = FakeEmbeddingProvider()
    vectors = provider.embed_documents(["hello world", "goodbye world", "third"])
    assert vectors.shape == (3, FAKE_DIMENSION)
    assert vectors.dtype == np.float32


def test_embed_query_returns_1d_vector_of_declared_dimension() -> None:
    provider = FakeEmbeddingProvider()
    vector = provider.embed_query("hello")
    assert vector.shape == (FAKE_DIMENSION,)
    assert provider.dimension == FAKE_DIMENSION


def test_embeddings_are_deterministic() -> None:
    provider = FakeEmbeddingProvider()
    v1 = provider.embed_query("photosynthesis")
    v2 = provider.embed_query("photosynthesis")
    assert np.allclose(v1, v2)


def test_different_text_yields_different_vector() -> None:
    provider = FakeEmbeddingProvider()
    v1 = provider.embed_query("photosynthesis")
    v2 = provider.embed_query("mitochondria")
    assert not np.allclose(v1, v2)


def test_embeddings_are_normalized() -> None:
    provider = FakeEmbeddingProvider()
    vector = provider.embed_query("hello")
    assert provider.normalizes_embeddings is True
    assert abs(float(np.linalg.norm(vector)) - 1.0) < 1e-5
