from app.benchmarking.report import (
    config_comparison_table,
    write_csv_table,
    write_json,
    write_markdown_table,
)


def make_results_dict():
    return {
        "A_bm25": {
            "5": {
                "aggregate": {
                    "reciprocal_rank": 0.5,
                    "recall_at_5": 0.6,
                    "precision_at_5": 0.4,
                    "ndcg_at_5": 0.55,
                    "hit_rate_at_5": 0.8,
                }
            }
        }
    }


def test_config_comparison_table_maps_mrr_to_reciprocal_rank():
    rows = config_comparison_table(make_results_dict(), top_k=5)
    assert rows[0]["configuration"] == "A_bm25"
    assert rows[0]["mrr"] == 0.5  # regression test: mrr must not silently default to 0.0
    assert rows[0]["recall_at_5"] == 0.6


def test_write_markdown_table_handles_empty_rows(tmp_path):
    path = tmp_path / "empty.md"
    write_markdown_table([], path, "Title")
    assert "No data" in path.read_text()


def test_write_markdown_table_renders_header_and_row(tmp_path):
    rows = [{"a": 1, "b": 2}]
    path = tmp_path / "out.md"
    write_markdown_table(rows, path, "My Table")
    text = path.read_text()
    assert "| a | b |" in text
    assert "| 1 | 2 |" in text


def test_write_csv_table_round_trips(tmp_path):
    import csv

    rows = [{"a": "1", "b": "2"}]
    path = tmp_path / "out.csv"
    write_csv_table(rows, path)
    with path.open() as f:
        read_rows = list(csv.DictReader(f))
    assert read_rows == rows


def test_write_json_produces_valid_json(tmp_path):
    import json

    path = tmp_path / "out.json"
    write_json({"a": 1}, path)
    assert json.loads(path.read_text()) == {"a": 1}
