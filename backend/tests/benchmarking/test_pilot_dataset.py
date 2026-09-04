from app.benchmarking.pilot_dataset import load_pilot_dataset


def test_pilot_dataset_loads_and_validates_clean():
    dataset = load_pilot_dataset()
    assert dataset.dataset_id == "pilot_v1"
    assert dataset.validate() == {}


def test_pilot_dataset_has_answerable_and_unanswerable_questions():
    dataset = load_pilot_dataset()
    answerable = [q for q in dataset.questions if q.answerable]
    unanswerable = [q for q in dataset.questions if not q.answerable]
    assert answerable
    assert unanswerable


def test_pilot_dataset_documents_match_question_source_documents():
    dataset = load_pilot_dataset()
    known_doc_ids = set(dataset.documents.values())
    for q in dataset.questions:
        for doc_id in q.source_documents:
            assert doc_id in known_doc_ids


def test_pilot_dataset_gold_chunk_ids_reference_their_own_document():
    dataset = load_pilot_dataset()
    for q in dataset.questions:
        for chunk_id in q.gold_chunk_ids:
            doc_id = chunk_id.split("::chunk::")[0]
            assert doc_id in q.source_documents
