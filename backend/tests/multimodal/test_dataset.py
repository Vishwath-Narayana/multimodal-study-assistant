from __future__ import annotations

from app.multimodal.evaluation.dataset import load_multimodal_eval_dataset


def test_load_multimodal_eval_dataset_parses_all_categories() -> None:
    dataset = load_multimodal_eval_dataset()
    categories = {q.category for q in dataset.queries}
    assert categories == {
        "text-only",
        "table",
        "image",
        "equation",
        "transcript",
        "mixed_text_image",
        "mixed_text_table",
        "mixed_document_audio",
    }


def test_load_multimodal_eval_dataset_equation_query_documents_limitation() -> None:
    dataset = load_multimodal_eval_dataset()
    equation_query = next(q for q in dataset.queries if q.category == "equation")
    assert equation_query.relevant_chunk_ids == []
    assert equation_query.note is not None


def test_load_multimodal_eval_dataset_populated_queries_have_relevant_chunks() -> None:
    dataset = load_multimodal_eval_dataset()
    for query in dataset.queries:
        if query.category == "equation":
            continue
        assert query.relevant_chunk_ids, f"{query.query_id} should have relevant chunk ids"
