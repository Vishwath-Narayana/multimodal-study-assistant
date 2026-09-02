"""The parser interface the rest of the system depends on.

See docs/decisions/ADR-004-model-agnostic-interfaces.md: nothing outside
this package should import a concrete parser's underlying library
directly. Today there is one implementation, :class:`DoclingParser`
(app.ingestion.parsers.docling_parser); future formats/parsers plug in
behind the same interface.
"""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

from app.ingestion.models import ParsedDocument


class DocumentParser(Protocol):
    """Converts a file on disk into the canonical :class:`ParsedDocument`."""

    def supports(self, file_type: str) -> bool: ...

    def parse(
        self, file_path: Path, *, document_id: str, filename: str, file_hash: str
    ) -> ParsedDocument: ...
