from __future__ import annotations

from app.study.duplicates import dedupe, normalize_text


def test_normalize_text_collapses_case_and_punctuation() -> None:
    assert normalize_text("What is BM25?!") == normalize_text("what is bm25")


def test_dedupe_drops_normalized_duplicates_preserving_first_seen_order() -> None:
    items = ["What is BM25?", "what is bm25", "What is TF-IDF?"]
    kept, duplicate_count = dedupe(items, key=lambda s: s)
    assert kept == ["What is BM25?", "What is TF-IDF?"]
    assert duplicate_count == 1


def test_dedupe_no_duplicates() -> None:
    items = ["a", "b", "c"]
    kept, duplicate_count = dedupe(items, key=lambda s: s)
    assert kept == items
    assert duplicate_count == 0
