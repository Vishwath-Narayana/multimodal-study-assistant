from __future__ import annotations

import pytest

from app.ingestion.models import BlockType
from app.retrieval.bm25_retriever import BM25Retriever
from app.retrieval.errors import NoIndexedChunksError
from tests.retrieval.conftest import make_chunk

CORPUS = [
    make_chunk("c1", "Photosynthesis converts light energy into chemical energy."),
    make_chunk("c2", "Cellular respiration releases energy stored in glucose."),
    make_chunk("c3", "The mitochondria is the powerhouse of the cell."),
    make_chunk("c4", "Photosynthesis occurs in chloroplasts within plant cells."),
]


def test_deterministic_ranking_and_expected_ordering() -> None:
    retriever = BM25Retriever.from_chunks(CORPUS)
    results = retriever.retrieve("photosynthesis energy", top_k=10)
    ids = [r.chunk_id for r in results]
    # c1 mentions both "photosynthesis" and "energy"; c4 mentions only
    # "photosynthesis"; c2 mentions only "energy" (of glucose); c3 mentions
    # neither term.
    assert ids[0] == "c1"
    assert "c3" not in ids[:2]


def test_empty_query_returns_no_candidates() -> None:
    retriever = BM25Retriever.from_chunks(CORPUS)
    assert retriever.retrieve("", top_k=5) == []
    assert retriever.retrieve("   ", top_k=5) == []


def test_top_k_is_respected() -> None:
    retriever = BM25Retriever.from_chunks(CORPUS)
    results = retriever.retrieve("cell", top_k=2)
    assert len(results) == 2


def test_top_k_zero_returns_empty() -> None:
    retriever = BM25Retriever.from_chunks(CORPUS)
    assert retriever.retrieve("cell", top_k=0) == []


def test_metadata_preservation() -> None:
    retriever = BM25Retriever.from_chunks(CORPUS)
    results = retriever.retrieve("mitochondria", top_k=1)
    assert results[0].chunk_id == "c3"
    assert results[0].document_id == "doc-1"
    assert results[0].content == CORPUS[2].content


def test_duplicate_chunk_ids_are_indexed_once() -> None:
    dup = make_chunk("c1", "A duplicate chunk id should not be indexed twice.")
    retriever = BM25Retriever.from_chunks([*CORPUS, dup])
    assert retriever.size == len(CORPUS)


def test_image_blocks_are_excluded_from_index() -> None:
    image_chunk = make_chunk("img1", "", chunk_type=BlockType.IMAGE)
    retriever = BM25Retriever.from_chunks([*CORPUS, image_chunk])
    assert retriever.size == len(CORPUS)


def test_empty_corpus_raises() -> None:
    with pytest.raises(NoIndexedChunksError):
        BM25Retriever.from_chunks([])


def test_all_content_less_chunks_raises() -> None:
    blanks = [make_chunk("b1", ""), make_chunk("b2", "   ")]
    with pytest.raises(NoIndexedChunksError):
        BM25Retriever.from_chunks(blanks)


def test_rebuild_produces_fresh_index() -> None:
    retriever = BM25Retriever.from_chunks(CORPUS[:2])
    assert retriever.size == 2
    rebuilt = retriever.rebuild(CORPUS)
    assert rebuilt.size == len(CORPUS)
    # original instance is untouched (no hidden mutation)
    assert retriever.size == 2


def test_deterministic_tie_breaking() -> None:
    # Two chunks with identical content -> identical scores; ranking must
    # break the tie by chunk_id, not by insertion order or randomness.
    tied = [
        make_chunk("z-chunk", "matching term matching term"),
        make_chunk("a-chunk", "matching term matching term"),
    ]
    retriever = BM25Retriever.from_chunks(tied)
    results = retriever.retrieve("matching", top_k=2)
    assert [r.chunk_id for r in results] == ["a-chunk", "z-chunk"]
