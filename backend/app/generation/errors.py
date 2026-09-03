"""Generation error types.

Mirrors `app.retrieval.errors`: a base class plus specific subclasses, each
carrying a `message` safe to surface to a caller. No generation error is
silently swallowed into a fallback (e.g. a provider outage never silently
becomes an abstention response — those are semantically different and are
kept distinct so a caller/operator can tell them apart).
"""

from __future__ import annotations


class GenerationError(Exception):
    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class EmptyQueryError(GenerationError):
    """The query string was empty/whitespace-only."""


class ProviderUnavailableError(GenerationError):
    """The configured LLM provider (e.g. Ollama) is unreachable."""


class GenerationFailedError(GenerationError):
    """The LLM provider was reachable but generation itself failed."""
