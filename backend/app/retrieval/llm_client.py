"""Minimal LLM client abstraction for HyDE.

One place HTTP calls to the local LLM backend happen — `HyDEExpander`
depends on `LLMClient`, never on `httpx`/Ollama's API shape directly, so the
backend is swappable (spec: "do not hardwire HTTP calls throughout
retrieval code, put them behind one client abstraction").

`OllamaClient` is the only production implementation, targeting a local
Ollama server (`Settings.ollama_base_url`, default
`http://localhost:11434`), preferred model `deepseek-r1:1.5b`
(`Settings.hyde_model`). Nothing here is called by CI or by the default
test suite — see `tests/retrieval/test_hyde.py`, which mocks `LLMClient`
entirely.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

import httpx


@dataclass
class GenerationParams:
    max_tokens: int
    temperature: float


class LLMClient(ABC):
    """Single-shot text generation, used only for HyDE passage generation."""

    @abstractmethod
    def is_reachable(self) -> bool:
        """Cheap health check; never raises."""

    @abstractmethod
    def generate(self, prompt: str, params: GenerationParams) -> str: ...

    @property
    @abstractmethod
    def model_id(self) -> str: ...


class OllamaClient(LLMClient):
    def __init__(self, base_url: str, model: str, timeout_seconds: float = 30.0) -> None:
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._timeout = timeout_seconds

    @property
    def model_id(self) -> str:
        return self._model

    def is_reachable(self) -> bool:
        try:
            response = httpx.get(f"{self._base_url}/api/tags", timeout=5.0)
            return response.status_code == 200
        except httpx.HTTPError:
            return False

    def generate(self, prompt: str, params: GenerationParams) -> str:
        response = httpx.post(
            f"{self._base_url}/api/generate",
            json={
                "model": self._model,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": params.temperature,
                    "num_predict": params.max_tokens,
                },
            },
            timeout=self._timeout,
        )
        response.raise_for_status()
        data = response.json()
        return str(data.get("response", "")).strip()
