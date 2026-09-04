"""FAISS index build/persist/load lifecycle.

**Index type**: `faiss.IndexFlatIP` (exact, brute-force inner-product
search). This is a research project over a small corpus — the spec
explicitly asks us not to prematurely optimize for approximate nearest
neighbor search, so an exact flat index is used rather than IVF/HNSW/PQ.

**Metric**: inner product. Combined with L2-normalized vectors (see
`embeddings.BGEEmbeddingProvider.normalizes_embeddings`), inner product over
unit vectors is mathematically equivalent to cosine similarity, which is
BGE's documented similarity metric.

**Dimension**: taken from the embedding provider (`provider.dimension`,
384 for bge-small-en-v1.5) — never hardcoded independently, so a dimension
mismatch between the provider and a stale index is caught rather than
silently producing garbage search results.

**Persistence layout** (`Settings.index_dir`, default `data/indexes/`):

    <index_dir>/faiss.index      -- the raw FAISS index (binary, gitignored)
    <index_dir>/manifest.json    -- IndexManifest, see below
    <index_dir>/id_map.json      -- FAISS vector position -> chunk_id

None of this is committed to git (see repo .gitignore).
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np

from app.ingestion.models import Chunk
from app.retrieval.corpus import eligible_chunks
from app.retrieval.embeddings import EmbeddingProvider
from app.retrieval.errors import (
    CorruptedManifestError,
    IndexNotBuiltError,
    NoIndexedChunksError,
    StaleIndexError,
)

if TYPE_CHECKING:
    # `faiss` bundles its own OpenMP runtime, which conflicts with the one
    # Docling/TableFormer's torch loads in-process (see
    # app/retrieval/__init__.py) — importing it eagerly at module load time
    # made every `app.main` import (and thus every document upload) pull it
    # in. Deferred to inside the methods that actually touch the `faiss`
    # module; this TYPE_CHECKING import is type-checker-only and never runs.
    import faiss

_INDEX_FILENAME = "faiss.index"
_MANIFEST_FILENAME = "manifest.json"
_ID_MAP_FILENAME = "id_map.json"
_INDEX_VERSION = 1


def _chunk_fingerprint(chunk: Chunk) -> str:
    """A stable hash of the parts of a chunk that affect its embedding.

    Used both to dedupe (a chunk id should never be embedded twice) and to
    detect staleness (if a chunk's content changed since the index was
    built, its fingerprint changes even though its id did not).
    """
    digest = hashlib.sha256()
    digest.update(chunk.id.encode("utf-8"))
    digest.update(b"\0")
    digest.update(chunk.content.encode("utf-8"))
    return digest.hexdigest()


@dataclass
class IndexManifest:
    embedding_model: str
    embedding_dimension: int
    index_type: str
    metric: str
    normalized: bool
    chunk_target_tokens: int
    chunk_overlap_tokens: int
    index_version: int
    created_at: str
    chunk_count: int
    chunk_fingerprints: dict[str, str] = field(default_factory=dict)

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2, sort_keys=True)

    @classmethod
    def from_json(cls, text: str) -> IndexManifest:
        try:
            data = json.loads(text)
            return cls(**data)
        except Exception as exc:  # noqa: BLE001
            raise CorruptedManifestError(f"Could not parse index manifest: {exc}") from exc


@dataclass
class FaissIndexStore:
    """Owns the on-disk FAISS index directory. Build / load / stale-check."""

    index_dir: Path

    @classmethod
    def build(
        cls,
        chunks: list[Chunk],
        embedding_provider: EmbeddingProvider,
        index_dir: str | Path,
        chunk_target_tokens: int,
        chunk_overlap_tokens: int,
    ) -> FaissIndexStore:
        import faiss

        eligible = eligible_chunks(chunks)
        if not eligible:
            raise NoIndexedChunksError(
                "No text-eligible chunks are available to build a FAISS index."
            )

        # Deterministic de-duplication by chunk id, same rule as BM25.
        seen: set[str] = set()
        deduped: list[Chunk] = []
        for chunk in eligible:
            if chunk.id in seen:
                continue
            seen.add(chunk.id)
            deduped.append(chunk)

        vectors = embedding_provider.embed_documents([c.content for c in deduped])
        if vectors.shape[1] != embedding_provider.dimension:
            raise NoIndexedChunksError(
                f"Embedding provider produced dimension {vectors.shape[1]}, "
                f"expected {embedding_provider.dimension}."
            )

        index = faiss.IndexFlatIP(embedding_provider.dimension)
        index.add(np.ascontiguousarray(vectors, dtype=np.float32))

        id_map = {str(i): c.id for i, c in enumerate(deduped)}
        manifest = IndexManifest(
            embedding_model=embedding_provider.model_id,
            embedding_dimension=embedding_provider.dimension,
            index_type="IndexFlatIP",
            metric="inner_product (cosine, via L2-normalized vectors)",
            normalized=embedding_provider.normalizes_embeddings,
            chunk_target_tokens=chunk_target_tokens,
            chunk_overlap_tokens=chunk_overlap_tokens,
            index_version=_INDEX_VERSION,
            created_at=datetime.now(UTC).isoformat(),
            chunk_count=len(deduped),
            chunk_fingerprints={c.id: _chunk_fingerprint(c) for c in deduped},
        )

        path = Path(index_dir)
        path.mkdir(parents=True, exist_ok=True)
        faiss.write_index(index, str(path / _INDEX_FILENAME))
        (path / _MANIFEST_FILENAME).write_text(manifest.to_json())
        (path / _ID_MAP_FILENAME).write_text(json.dumps(id_map, indent=2))

        store = cls(index_dir=path)
        store._index = index
        store._id_map = id_map
        store._manifest = manifest
        store._chunks_by_id = {c.id: c for c in deduped}
        return store

    def __post_init__(self) -> None:
        self._index: faiss.Index | None = None
        self._id_map: dict[str, str] | None = None
        self._manifest: IndexManifest | None = None
        self._chunks_by_id: dict[str, Chunk] | None = None

    def exists(self) -> bool:
        return (self.index_dir / _INDEX_FILENAME).exists() and (
            self.index_dir / _MANIFEST_FILENAME
        ).exists()

    def load(self, chunks_by_id: dict[str, Chunk] | None = None) -> FaissIndexStore:
        """Load a previously built index from disk. `chunks_by_id`, if
        given, lets callers supply fresh chunk content (e.g. for staleness
        checks); otherwise search results carry only what the id map + a
        provided chunk lookup can supply."""
        import faiss

        if not self.exists():
            raise IndexNotBuiltError(
                f"No FAISS index found at {self.index_dir}. Build it first."
            )
        manifest_text = (self.index_dir / _MANIFEST_FILENAME).read_text()
        self._manifest = IndexManifest.from_json(manifest_text)
        try:
            id_map_raw = json.loads((self.index_dir / _ID_MAP_FILENAME).read_text())
        except Exception as exc:  # noqa: BLE001
            raise CorruptedManifestError(f"Could not parse FAISS id map: {exc}") from exc
        self._id_map = id_map_raw
        self._index = faiss.read_index(str(self.index_dir / _INDEX_FILENAME))
        self._chunks_by_id = chunks_by_id
        return self

    @property
    def manifest(self) -> IndexManifest:
        if self._manifest is None:
            raise IndexNotBuiltError("Index manifest not loaded; call load() or build() first.")
        return self._manifest

    def is_stale(self, current_chunks: list[Chunk]) -> bool:
        """True if the current eligible-chunk set differs (by id or content)
        from what the index was built from."""
        manifest = self.manifest
        current_eligible = eligible_chunks(current_chunks)
        current_fp = {c.id: _chunk_fingerprint(c) for c in current_eligible}
        return current_fp != manifest.chunk_fingerprints

    def search(self, query_vector: np.ndarray, top_k: int) -> list[tuple[str, float]]:
        """Returns `(chunk_id, similarity_score)` best-first."""
        if self._index is None or self._id_map is None:
            raise IndexNotBuiltError("FAISS index not loaded; call load() or build() first.")
        if top_k <= 0 or self._index.ntotal == 0:
            return []
        query = np.ascontiguousarray(query_vector, dtype=np.float32).reshape(1, -1)
        k = min(top_k, self._index.ntotal)
        scores, indices = self._index.search(query, k)
        results: list[tuple[str, float]] = []
        for score, idx in zip(scores[0], indices[0], strict=True):
            if idx < 0:
                continue
            chunk_id = self._id_map[str(int(idx))]
            results.append((chunk_id, float(score)))
        return results

    def raise_if_stale(self, current_chunks: list[Chunk]) -> None:
        if self.is_stale(current_chunks):
            raise StaleIndexError(
                "FAISS index no longer matches the current chunk set; rebuild required."
            )
