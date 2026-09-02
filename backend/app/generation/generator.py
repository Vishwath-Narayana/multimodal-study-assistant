"""`Generator` implementations.

`OllamaGenerator` is the only production implementation, targeting the same
local Ollama server Phase 2's HyDE client uses (`app.retrieval.llm_client`)
— reused as-is rather than duplicated, since it is already a generic
single-shot "prompt in, text out" abstraction with no HyDE-specific
assumptions baked in. `LLM_PROVIDER=ollama` / `LLM_MODEL=deepseek-r1:8b` is
the intended production configuration (`app.core.config.Settings`), but
`OllamaGenerator` itself only depends on the `LLMClient` ABC, so a different
`LLMClient` implementation would work without changing this class.

Nothing here is exercised by the default test suite (see
`tests/generation/fakes.py::FakeGenerator`) or by CI — real generation
requires a reachable Ollama server with the model already pulled.
"""

from __future__ import annotations

import httpx

from app.generation.citations import extract_citations
from app.generation.errors import GenerationFailedError, ProviderUnavailableError
from app.generation.interfaces import Generator
from app.generation.models import GeneratedAnswer
from app.generation.prompts import render_grounded_prompt
from app.retrieval.llm_client import GenerationParams, LLMClient
from app.retrieval.models import RetrievalResult


class OllamaGenerator(Generator):
    def __init__(self, client: LLMClient) -> None:
        self._client = client

    @property
    def provider_id(self) -> str:
        return "ollama"

    @property
    def model_id(self) -> str:
        return self._client.model_id

    def generate(
        self, query: str, evidence: list[RetrievalResult], params: GenerationParams
    ) -> GeneratedAnswer:
        if not self._client.is_reachable():
            raise ProviderUnavailableError(
                f"LLM provider '{self.provider_id}' (model '{self.model_id}') is unreachable. "
                "Is Ollama running and is the model pulled?"
            )
        prompt = render_grounded_prompt(query, evidence)
        try:
            text = self._client.generate(prompt, params)
        except httpx.HTTPError as exc:
            raise GenerationFailedError(f"Generation request failed: {exc}") from exc
        return GeneratedAnswer(text=text, raw_chunk_ids=extract_citations(text))
