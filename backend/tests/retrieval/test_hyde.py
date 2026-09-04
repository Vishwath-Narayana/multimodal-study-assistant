from __future__ import annotations

import pytest

from app.retrieval.errors import HyDEUnavailableError
from app.retrieval.hyde import HyDEExpander
from app.retrieval.llm_client import GenerationParams, LLMClient


class MockLLMClient(LLMClient):
    def __init__(self, reachable: bool = True, response: str = "A hypothetical passage.") -> None:
        self._reachable = reachable
        self._response = response
        self.last_prompt: str | None = None
        self.last_params: GenerationParams | None = None

    @property
    def model_id(self) -> str:
        return "mock-model"

    def is_reachable(self) -> bool:
        return self._reachable

    def generate(self, prompt: str, params: GenerationParams) -> str:
        self.last_prompt = prompt
        self.last_params = params
        return self._response


def test_expand_returns_generated_passage_and_model_metadata() -> None:
    client = MockLLMClient(response="Photosynthesis converts light into chemical energy.")
    expander = HyDEExpander(client, max_tokens=256, temperature=0.2)
    result = expander.expand("What is photosynthesis?")
    assert result.expanded_text == "Photosynthesis converts light into chemical energy."
    assert result.model == "mock-model"
    assert result.original_query == "What is photosynthesis?"
    assert result.generation_params == {"max_tokens": 256, "temperature": 0.2}


def test_expand_includes_query_in_prompt_not_retrieved_content() -> None:
    client = MockLLMClient()
    expander = HyDEExpander(client, max_tokens=256, temperature=0.2)
    expander.expand("What is mitosis?")
    assert client.last_prompt is not None
    assert "What is mitosis?" in client.last_prompt


def test_model_unavailable_raises_explicit_error() -> None:
    client = MockLLMClient(reachable=False)
    expander = HyDEExpander(client, max_tokens=256, temperature=0.2)
    with pytest.raises(HyDEUnavailableError):
        expander.expand("anything")


def test_is_available_reflects_client_reachability() -> None:
    assert HyDEExpander(MockLLMClient(reachable=True), 256, 0.2).is_available() is True
    assert HyDEExpander(MockLLMClient(reachable=False), 256, 0.2).is_available() is False


def test_empty_generated_text_raises() -> None:
    client = MockLLMClient(response="   ")
    expander = HyDEExpander(client, max_tokens=256, temperature=0.2)
    with pytest.raises(HyDEUnavailableError):
        expander.expand("anything")


def test_generation_exception_is_wrapped() -> None:
    class RaisingClient(MockLLMClient):
        def generate(self, prompt: str, params: GenerationParams) -> str:
            raise RuntimeError("connection reset")

    with pytest.raises(HyDEUnavailableError):
        HyDEExpander(RaisingClient(), 256, 0.2).expand("anything")
