"""Table-aware representation helpers (spec section 11/12).

`Chunk.table_content` (the raw `list[list[str]]` grid, Phase 1) already
preserves table structure and is already indexed for retrieval — Phase 1's
`DoclingParser`/`chunking.py` did not need replacing (spec: "do not replace
existing reliable table extraction with a new parser without evidence it
is necessary"). This module adds the structured view and richer searchable
text described in the Phase 4 spec on top of that existing grid, formalized
as a first-class helper rather than left as an ad hoc join at each call
site.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class TableData:
    """A grid split into a header row and body rows.

    Heuristic: the first grid row is treated as the header row when the
    grid has more than one row; a single-row "table" has no distinct
    header. This is a documented assumption, not a claim that Docling
    marks header rows explicitly (it does not expose that on the grid this
    project consumes) — see docs/architecture/multimodal.md "Limitations".
    """

    headers: list[str]
    rows: list[list[str]]

    @classmethod
    def from_grid(cls, grid: list[list[str]]) -> TableData:
        if not grid:
            return cls(headers=[], rows=[])
        if len(grid) == 1:
            return cls(headers=[], rows=[list(grid[0])])
        return cls(headers=list(grid[0]), rows=[list(row) for row in grid[1:]])


def build_table_searchable_text(grid: list[list[str]], *, surrounding_text: str = "") -> str:
    """Column headers + row labels/values + surrounding context, so a query
    like "What is the value of X in 2024?" can match on header/cell text
    (spec section 12) even before any reranking happens."""
    table = TableData.from_grid(grid)
    parts: list[str] = []
    if table.headers:
        parts.append("Columns: " + " | ".join(table.headers))
    for row in table.rows:
        parts.append(" | ".join(row))
    if surrounding_text.strip():
        parts.append(surrounding_text.strip())
    return "\n".join(p for p in parts if p)
