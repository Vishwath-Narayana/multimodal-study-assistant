"""Real-Ollama HyDE integration test.

Not run by default (see `[tool.pytest.ini_options] addopts` in
pyproject.toml, which deselects `requires_ollama` unless explicitly
included) and additionally self-skips if Ollama is not actually reachable,
so it never blocks CI or a machine without Ollama installed.
"""

from __future__ import annotations

import httpx
import pytest

from app.core.config import get_settings
from app.retrieval.hyde import HyDEExpander
from app.retrieval.llm_client import OllamaClient


def _ollama_reachable(base_url: str) -> bool:
    try:
        return httpx.get(f"{base_url}/api/tags", timeout=2.0).status_code == 200
    except httpx.HTTPError:
        return False


@pytest.mark.requires_ollama
def test_real_ollama_generates_a_hyde_passage() -> None:
    settings = get_settings()
    if not _ollama_reachable(settings.ollama_base_url):
        pytest.skip("Ollama is not reachable at the configured base URL.")

    client = OllamaClient(
        settings.ollama_base_url, settings.hyde_model, settings.hyde_timeout_seconds
    )
    expander = HyDEExpander(client, settings.hyde_max_tokens, settings.hyde_temperature)
    result = expander.expand("What is photosynthesis?")
    assert result.expanded_text
    assert result.model == settings.hyde_model
