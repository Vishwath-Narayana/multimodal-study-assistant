"""Study Engine error types.

Mirrors `app.generation.errors`/`app.retrieval.errors`: a base class plus
specific subclasses, each carrying a `message` safe to surface to a caller.
No error here is silently swallowed into a fallback — a malformed LLM
output never silently becomes an empty-but-200 response, and a provider
outage never silently becomes an abstention (those are semantically
different and must stay distinguishable to a caller/operator).
"""

from __future__ import annotations


class StudyError(Exception):
    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class EmptyQueryError(StudyError):
    """The query/topic string was empty/whitespace-only."""


class InvalidRequestError(StudyError):
    """A request parameter (count, difficulty, scope, ...) was invalid."""


class ProviderUnavailableError(StudyError):
    """The configured LLM provider (e.g. Ollama) is unreachable."""


class GenerationFailedError(StudyError):
    """The LLM provider was reachable but generation itself failed."""


class MalformedStudyOutputError(StudyError):
    """The model's output could not be parsed into the requested structured
    shape (e.g. invalid/absent JSON for a quiz/MCQ/flashcards/comparison
    request). Per spec: "If parsing fails: return a controlled generation/
    validation error" — never silently return malformed data."""
