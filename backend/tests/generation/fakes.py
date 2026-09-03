"""Deterministic test doubles for generation components, so the default
test suite never needs a reachable Ollama server or a real model."""

from __future__ import annotations

import httpx

from app.generation.errors import GenerationFailedError, ProviderUnavailableError
from app.generation.interfaces import Generator
from app.generation.models import GeneratedAnswer
from app.retrieval.llm_client import GenerationParams, LLMClient
from app.retrieval.models import RetrievalResult


class FakeLLMClient(LLMClient):
    def __init__(
        self,
        reachable: bool = True,
        response_text: str = "A fake generated answer.",
        raise_on_generate: bool = False,
        model: str = "fake-model",
    ) -> None:
        self._reachable = reachable
        self._response_text = response_text
        self._raise_on_generate = raise_on_generate
        self._model = model

    def is_reachable(self) -> bool:
        return self._reachable

    def generate(self, prompt: str, params: GenerationParams) -> str:
        if self._raise_on_generate:
            raise httpx.HTTPError("simulated failure")
        return self._response_text

    @property
    def model_id(self) -> str:
        return self._model


class FakeGenerator(Generator):
    """Mocked `Generator` — returns a canned answer, no LLM call at all."""

    def __init__(
        self,
        text: str = "A fake generated answer. [chunk:c1]",
        raw_chunk_ids: list[str] | None = None,
        unavailable: bool = False,
        fails: bool = False,
        provider: str = "fake",
        model: str = "fake-model",
    ) -> None:
        self._text = text
        self._raw_chunk_ids = raw_chunk_ids if raw_chunk_ids is not None else ["c1"]
        self._unavailable = unavailable
        self._fails = fails
        self._provider = provider
        self._model = model

    @property
    def provider_id(self) -> str:
        return self._provider

    @property
    def model_id(self) -> str:
        return self._model

    def generate(
        self, query: str, evidence: list[RetrievalResult], params: GenerationParams
    ) -> GeneratedAnswer:
        if self._unavailable:
            raise ProviderUnavailableError("Fake provider is configured as unavailable.")
        if self._fails:
            raise GenerationFailedError("Fake provider is configured to fail generation.")
        return GeneratedAnswer(text=self._text, raw_chunk_ids=self._raw_chunk_ids)
