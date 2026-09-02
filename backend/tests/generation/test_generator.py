from __future__ import annotations

import pytest

from app.generation.errors import GenerationFailedError, ProviderUnavailableError
from app.generation.generator import OllamaGenerator
from app.retrieval.llm_client import GenerationParams
from tests.generation.conftest import make_result
from tests.generation.fakes import FakeLLMClient

EVIDENCE = [make_result("c1", "Photosynthesis converts light energy into chemical energy.")]
PARAMS = GenerationParams(max_tokens=128, temperature=0.0)


def test_generate_success_extracts_citations() -> None:
    client = FakeLLMClient(response_text="Photosynthesis makes energy. [chunk:c1]")
    generator = OllamaGenerator(client)
    result = generator.generate("What is photosynthesis?", EVIDENCE, PARAMS)
    assert result.text == "Photosynthesis makes energy. [chunk:c1]"
    assert result.raw_chunk_ids == ["c1"]
    assert generator.provider_id == "ollama"
    assert generator.model_id == "fake-model"


def test_generate_raises_when_provider_unreachable() -> None:
    client = FakeLLMClient(reachable=False)
    generator = OllamaGenerator(client)
    with pytest.raises(ProviderUnavailableError):
        generator.generate("What is photosynthesis?", EVIDENCE, PARAMS)


def test_generate_raises_when_generation_call_fails() -> None:
    client = FakeLLMClient(raise_on_generate=True)
    generator = OllamaGenerator(client)
    with pytest.raises(GenerationFailedError):
        generator.generate("What is photosynthesis?", EVIDENCE, PARAMS)


def test_generate_with_no_citations_in_output() -> None:
    client = FakeLLMClient(response_text="An answer with no citation markers at all.")
    generator = OllamaGenerator(client)
    result = generator.generate("What is photosynthesis?", EVIDENCE, PARAMS)
    assert result.raw_chunk_ids == []
