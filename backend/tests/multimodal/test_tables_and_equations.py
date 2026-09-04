from __future__ import annotations

from app.multimodal.equations import build_equation_representation
from app.multimodal.tables import TableData, build_table_searchable_text


def test_table_data_from_grid_splits_header_and_rows() -> None:
    grid = [["Year", "Revenue"], ["2023", "100"], ["2024", "150"]]
    table = TableData.from_grid(grid)
    assert table.headers == ["Year", "Revenue"]
    assert table.rows == [["2023", "100"], ["2024", "150"]]


def test_table_data_from_grid_single_row_has_no_header() -> None:
    table = TableData.from_grid([["only", "row"]])
    assert table.headers == []
    assert table.rows == [["only", "row"]]


def test_table_data_from_grid_empty() -> None:
    table = TableData.from_grid([])
    assert table.headers == []
    assert table.rows == []


def test_build_table_searchable_text_includes_headers_and_values() -> None:
    grid = [["Year", "Revenue"], ["2024", "150"]]
    text = build_table_searchable_text(grid)
    assert "Year" in text
    assert "Revenue" in text
    assert "2024" in text
    assert "150" in text


def test_build_table_searchable_text_includes_surrounding_context() -> None:
    grid = [["Year", "Revenue"], ["2024", "150"]]
    text = build_table_searchable_text(grid, surrounding_text="Quarterly earnings report")
    assert "Quarterly earnings report" in text


def test_build_equation_representation_preserves_original() -> None:
    result = build_equation_representation("E = mc^2")
    assert result.original_representation == "E = mc^2"
    assert "E = mc^2" in result.searchable_text


def test_build_equation_representation_includes_surrounding_text() -> None:
    result = build_equation_representation("E = mc^2", surrounding_text="Mass-energy equivalence")
    assert "Mass-energy equivalence" in result.searchable_text
