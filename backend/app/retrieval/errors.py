"""Retrieval error types.

Mirrors `app.ingestion.errors`: a base class plus a small set of specific
subclasses, each carrying a `message` that is safe to surface to a caller
(never a raw internal exception/traceback string). No retrieval error is
silently swallowed into a fallback mode unless a caller explicitly asked for
one (see docs/architecture/retrieval.md "Error Behavior").
"""

from __future__ import annotations


class RetrievalError(Exception):
    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class EmptyQueryError(RetrievalError):
    """The query string was empty/whitespace-only."""


class QueryTooLongError(RetrievalError):
    """The query string exceeded the configured maximum length (spec
    section 8G: reject pathologically long input, without restricting
    legitimate academic questions)."""


class InvalidQueryError(RetrievalError):
    """The query contains control characters that have no legitimate use
    in a question and could otherwise reach logs/prompts unescaped."""


class InvalidTopKError(RetrievalError):
    """The requested `top_k` was outside the allowed range."""


class InvalidModeError(RetrievalError):
    """An unrecognized retrieval mode was requested."""


class NoIndexedChunksError(RetrievalError):
    """No chunks are available to index/search (corpus empty)."""


class IndexNotBuiltError(RetrievalError):
    """A FAISS index was requested but has not been built yet."""


class StaleIndexError(RetrievalError):
    """The on-disk FAISS index no longer matches the current chunk set."""


class CorruptedManifestError(RetrievalError):
    """The FAISS index manifest could not be parsed/validated."""


class EmbeddingModelError(RetrievalError):
    """The embedding model failed to load or run."""


class RerankerModelError(RetrievalError):
    """The cross-encoder reranker model failed to load or run."""


class HyDEUnavailableError(RetrievalError):
    """HyDE was requested but the configured LLM backend is unreachable."""
