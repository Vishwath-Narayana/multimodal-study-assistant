"""Real-Ollama grounded-generation integration test.

Not run by default (`requires_ollama` is deselected in `pyproject.toml`'s
`addopts`) and additionally self-skips if Ollama is not reachable or the
configured model has not been pulled, so it never blocks CI or a machine
without Ollama/DeepSeek-R1 installed. See docs/architecture/generation.md
"Ollama setup" for how to run this manually.
"""

from __future__ import annotations

import httpx
import pytest

from app.core.config import get_settings
from app.generation.generator import OllamaGenerator
from app.retrieval.llm_client import GenerationParams, OllamaClient
from app.retrieval.models import RetrievalResult, RetrievalSource


def _ollama_reachable(base_url: str) -> bool:
    try:
        return httpx.get(f"{base_url}/api/tags", timeout=2.0).status_code == 200
    except httpx.HTTPError:
        return False


@pytest.mark.requires_ollama
def test_real_ollama_generates_a_grounded_answer() -> None:
    settings = get_settings()
    if not _ollama_reachable(settings.ollama_base_url):
        pytest.skip("Ollama is not reachable at the configured base URL.")

    client = OllamaClient(
        settings.ollama_base_url, settings.llm_model, settings.generation_timeout_seconds
    )
    if not client.is_reachable():
        pytest.skip(f"Ollama model '{settings.llm_model}' is not available.")

    generator = OllamaGenerator(client)
    evidence = [
        RetrievalResult(
            chunk_id="c1",
            document_id="doc-1",
            content=(
                "Photosynthesis is the process by which plants convert light energy "
                "into chemical energy stored in glucose."
            ),
            score=1.0,
            rank=1,
            retrieval_source=RetrievalSource.RERANKER,
        )
    ]
    params = GenerationParams(
        max_tokens=settings.generation_max_tokens, temperature=settings.generation_temperature
    )
    result = generator.generate("What is photosynthesis?", evidence, params)
    assert result.text
