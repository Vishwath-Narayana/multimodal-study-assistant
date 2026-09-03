"""Lightweight, deterministic duplicate detection (spec section 27).

Normalized-exact-text only — no semantic/embedding-based deduplication
model is introduced solely for this (spec: "Do not introduce a heavyweight
semantic deduplication model"). This will miss paraphrased near-duplicates;
see docs/architecture/study-engine.md "Limitations".
"""

from __future__ import annotations

import re
from collections.abc import Callable

_WHITESPACE_OR_PUNCT = re.compile(r"[^a-z0-9]+")


def normalize_text(text: str) -> str:
    """Lowercase, strip punctuation, collapse whitespace — for exact
    near-duplicate comparison only, not a similarity score."""
    return _WHITESPACE_OR_PUNCT.sub(" ", text.lower()).strip()


def dedupe[T](items: list[T], key: Callable[[T], str]) -> tuple[list[T], int]:
    """Drop items whose normalized `key(item)` was already seen, preserving
    first-seen order. Returns (kept_items, duplicate_count)."""
    seen: set[str] = set()
    kept: list[T] = []
    duplicate_count = 0
    for item in items:
        normalized = normalize_text(key(item))
        if normalized in seen:
            duplicate_count += 1
            continue
        seen.add(normalized)
        kept.append(item)
    return kept, duplicate_count
