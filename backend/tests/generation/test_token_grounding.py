from __future__ import annotations

from app.generation.models import TokenGroundingTier
from app.generation.token_grounding import DeterministicTokenGrounder
from tests.generation.conftest import make_result

EVIDENCE = [make_result("c1", "Photosynthesis converts light energy into chemical energy.")]


def test_exact_match_scores_highest() -> None:
    grounder = DeterministicTokenGrounder()
    result = grounder.ground("Photosynthesis converts light energy.", EVIDENCE)
    exact_tokens = [d for d in result.details if d.tier == TokenGroundingTier.EXACT]
    assert exact_tokens
    assert all(d.score == 1.0 for d in exact_tokens)


def test_stem_match_scores_second_tier() -> None:
    grounder = DeterministicTokenGrounder()
    # "converts" is in evidence; "converting" should stem-match it.
    result = grounder.ground("The process is converting energy.", EVIDENCE)
    tiers = {d.token: d.tier for d in result.details}
    assert tiers.get("converting") in (TokenGroundingTier.STEM, TokenGroundingTier.EXACT)


def test_substring_match() -> None:
    grounder = DeterministicTokenGrounder()
    evidence = [make_result("c1", "photosynthesis")]
    result = grounder.ground("synthesis", evidence)
    assert result.details[0].tier == TokenGroundingTier.SUBSTRING
    assert result.details[0].score == 0.8


def test_ungrounded_content_scores_lowest() -> None:
    grounder = DeterministicTokenGrounder()
    result = grounder.ground("xenomorph zzqvt unrelated gibberish term.", EVIDENCE)
    assert all(d.tier == TokenGroundingTier.UNGROUNDED for d in result.details)
    assert all(d.score == 0.2 for d in result.details)


def test_grounding_ratio_is_mean_of_token_scores() -> None:
    grounder = DeterministicTokenGrounder()
    result = grounder.ground("Photosynthesis xenomorph.", EVIDENCE)
    expected = sum(d.score for d in result.details) / len(result.details)
    assert abs(result.grounding_ratio - expected) < 1e-9


def test_punctuation_and_case_do_not_affect_grounding() -> None:
    grounder = DeterministicTokenGrounder()
    lower = grounder.ground("photosynthesis converts light energy", EVIDENCE)
    upper_punct = grounder.ground("PHOTOSYNTHESIS, converts! light; energy?", EVIDENCE)
    assert lower.grounding_ratio == upper_punct.grounding_ratio


def test_stopwords_excluded_from_token_count() -> None:
    grounder = DeterministicTokenGrounder()
    result = grounder.ground("the a an of", EVIDENCE)
    assert result.total_token_count == 0
    assert result.grounding_ratio == 0.0


def test_empty_answer_returns_zero_ratio() -> None:
    grounder = DeterministicTokenGrounder()
    result = grounder.ground("", EVIDENCE)
    assert result.grounding_ratio == 0.0
    assert result.total_token_count == 0
