"""BM25 tokenization.

**Baseline behavior**: lowercasing and splitting on non-alphanumeric
characters. This is the minimal, standard preprocessing BM25 implementations
typically assume — not an EduRAG-specified value, but a widely-used default
we adopt rather than invent something more aggressive.

**Implementation choices** (documented individually so it is clear none of
these were silently added):
- No stopword removal. Removing stopwords can hurt short/definitional
  queries ("what is X") without demonstrated benefit here, so we keep the
  full token stream — "avoid excessive preprocessing without evidence" per
  the Phase 2 spec.
- No stemming/lemmatization. Same reasoning — stemming is a further
  preprocessing step with no evidence it helps this corpus, and it would
  make BM25 term matches harder to explain/debug in a research context.
- Numbers and alphanumeric tokens (e.g. "co2", "1.5") are kept as single
  tokens; punctuation is treated purely as a separator, not preserved.

This module is the single place tokenization happens for BM25 — both index
build and query time call the same function, so index/query tokenization can
never drift apart.
"""

from __future__ import annotations

import re

_TOKEN_PATTERN = re.compile(r"[a-z0-9]+")


def tokenize(text: str) -> list[str]:
    """Lowercase + split on runs of non-alphanumeric characters.

    Deterministic and side-effect-free. An empty/whitespace-only string
    returns an empty list rather than raising.
    """
    return _TOKEN_PATTERN.findall(text.lower())
