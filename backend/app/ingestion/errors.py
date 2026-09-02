"""Ingestion-specific exceptions.

These carry a safe, user-facing ``message`` separate from any internal
detail so the API layer never has to guess what is safe to expose (see
docs/research/security.md).
"""

from __future__ import annotations


class IngestionError(Exception):
    """Base class for all ingestion failures."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class ValidationError(IngestionError):
    """The uploaded file failed validation before parsing was attempted."""


class ParserError(IngestionError):
    """The document parser could not produce a canonical representation."""


class StorageError(IngestionError):
    """Reading or writing ingestion-related files/paths failed."""
