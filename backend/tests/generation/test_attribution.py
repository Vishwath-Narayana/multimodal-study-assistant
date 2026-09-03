from __future__ import annotations

from app.generation.attribution import DeterministicChunkAttributor
from tests.generation.conftest import make_result


def test_attribution_ranks_higher_relevance_and_overlap_first() -> None:
    attributor = DeterministicChunkAttributor()
    evidence = [
        make_result(
            "c1", "Photosynthesis converts light energy into chemical energy.", rerank_score=1.0
        ),
        make_result(
            "c2", "Unrelated content about cooking recipes and kitchens.", rerank_score=-2.0
        ),
    ]
    answer = "Photosynthesis converts light energy into chemical energy. [chunk:c1]"
    scores = attributor.attribute(answer, evidence)
    assert [s.chunk_id for s in scores] == ["c1", "c2"]
    assert scores[0].rank == 1
    assert scores[0].attribution_score > scores[1].attribution_score


def test_attribution_is_empty_for_no_evidence() -> None:
    attributor = DeterministicChunkAttributor()
    assert attributor.attribute("Some answer.", []) == []


def test_attribution_falls_back_to_score_when_no_rerank_score() -> None:
    attributor = DeterministicChunkAttributor()
    evidence = [
        make_result("c1", "Photosynthesis converts light energy.", score=5.0, rerank_score=None),
        make_result("c2", "Unrelated cooking content.", score=1.0, rerank_score=None),
    ]
    scores = attributor.attribute("Photosynthesis converts light energy. [chunk:c1]", evidence)
    assert scores[0].chunk_id == "c1"


def test_attribution_deterministic_given_same_inputs() -> None:
    attributor = DeterministicChunkAttributor()
    evidence = [
        make_result("c1", "Photosynthesis converts light energy.", rerank_score=1.0),
        make_result("c2", "Cellular respiration releases energy.", rerank_score=1.0),
    ]
    answer = "Both processes involve energy. [chunk:c1] [chunk:c2]"
    first = attributor.attribute(answer, evidence)
    second = attributor.attribute(answer, evidence)
    assert [(s.chunk_id, s.attribution_score, s.rank) for s in first] == [
        (s.chunk_id, s.attribution_score, s.rank) for s in second
    ]


def test_attribution_ties_broken_by_chunk_id() -> None:
    attributor = DeterministicChunkAttributor()
    evidence = [
        make_result("z1", "identical text content here", rerank_score=1.0),
        make_result("a1", "identical text content here", rerank_score=1.0),
    ]
    scores = attributor.attribute("identical text content here", evidence)
    assert [s.chunk_id for s in scores] == ["a1", "z1"]
