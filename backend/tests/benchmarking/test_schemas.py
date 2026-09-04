from app.benchmarking.schemas import BenchmarkDataset, BenchmarkQuestion, Modality, QuestionCategory


def make_question(**overrides) -> BenchmarkQuestion:
    defaults = dict(
        question_id="q1",
        question="What is X?",
        category=QuestionCategory.FACTUAL,
        modality=Modality.TEXT,
        answerable=True,
        gold_chunk_ids=["doc1::chunk::00001"],
    )
    defaults.update(overrides)
    return BenchmarkQuestion(**defaults)


def test_valid_question_has_no_problems():
    assert make_question().validate() == []


def test_empty_question_id_is_a_problem():
    problems = make_question(question_id="").validate()
    assert "question_id is empty" in problems


def test_empty_question_text_is_a_problem():
    problems = make_question(question="   ").validate()
    assert "question is empty" in problems


def test_answerable_without_gold_chunks_is_a_problem():
    problems = make_question(answerable=True, gold_chunk_ids=[]).validate()
    assert "answerable=True but gold_chunk_ids is empty" in problems


def test_unanswerable_with_gold_chunks_is_a_problem():
    problems = make_question(answerable=False, gold_chunk_ids=["x::chunk::1"]).validate()
    assert "answerable=False but gold_chunk_ids is non-empty" in problems


def test_unanswerable_category_must_have_answerable_false():
    problems = make_question(
        category=QuestionCategory.UNANSWERABLE, answerable=True, gold_chunk_ids=["x::chunk::1"]
    ).validate()
    assert "category=unanswerable but answerable=True" in problems


def test_round_trip_to_dict_and_back():
    q = make_question(note="a note")
    restored = BenchmarkQuestion.from_dict(q.to_dict())
    assert restored == q


def test_dataset_validate_catches_duplicate_ids():
    dataset = BenchmarkDataset(
        dataset_id="d1",
        description="test",
        documents={"doc1": "hash1"},
        questions=[make_question(question_id="q1"), make_question(question_id="q1")],
    )
    problems = dataset.validate()
    assert "q1" in problems
    assert "duplicate question_id" in problems["q1"]


def test_dataset_stats_counts_by_category_and_modality():
    dataset = BenchmarkDataset(
        dataset_id="d1",
        description="test",
        documents={"doc1": "hash1"},
        questions=[
            make_question(
                question_id="q1", category=QuestionCategory.FACTUAL, modality=Modality.TEXT
            ),
            make_question(
                question_id="q2",
                category=QuestionCategory.UNANSWERABLE,
                answerable=False,
                gold_chunk_ids=[],
                modality=Modality.TEXT,
            ),
        ],
    )
    stats = dataset.stats()
    assert stats["question_count"] == 2
    assert stats["answerable_count"] == 1
    assert stats["unanswerable_count"] == 1
    assert stats["by_category"] == {"factual": 1, "unanswerable": 1}
    assert stats["by_modality"] == {"text": 2}
