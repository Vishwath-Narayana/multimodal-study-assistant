"""Equation/formula representation helper (spec section 13).

Phase 1's `DoclingParser` already defines `BlockType.EQUATION` and
`DocumentBlock.equation_content`/`Chunk.equation_content` end-to-end (see
docs/architecture/ingestion.md §4) but leaves `equation_content` as raw
text, because Docling's formula-enrichment model (which would produce
LaTeX/MathML) is deliberately disabled — an explicit Phase 1 decision kept
unchanged in Phase 4 (spec section 36: "do not silently change Phase 1
chunking"). This module does not add a new equation parser; it documents
and formalizes the existing representation rather than fabricating a
LaTeX/MathML form that was never actually produced.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class EquationRepresentation:
    """The representation actually available for one equation chunk.

    `original_representation` is whatever Docling produced verbatim
    (currently: plain extracted text, since formula enrichment is
    disabled — never LaTeX/MathML in this environment).
    `searchable_text` combines it with surrounding explanatory text so the
    equation is matchable by nearby prose, not just its own (often
    symbol-heavy, low-recall) text.
    """

    original_representation: str
    searchable_text: str


def build_equation_representation(
    equation_content: str, *, surrounding_text: str = ""
) -> EquationRepresentation:
    parts = [equation_content.strip()]
    if surrounding_text.strip():
        parts.append(surrounding_text.strip())
    return EquationRepresentation(
        original_representation=equation_content,
        searchable_text="\n".join(p for p in parts if p),
    )
