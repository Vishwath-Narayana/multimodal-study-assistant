"""HyDE (Hypothetical Document Embeddings) query expansion.

`HyDEExpander` implements `QueryExpander`: given the user's original query
(never retrieved document content — see docs/research/security.md), asks
the configured `LLMClient` for a short hypothetical passage, which
`HybridRetriever` then embeds and searches FAISS with. BM25 never sees this
text (enforced in `hybrid.py`, not here).

If the backend is unreachable, `expand()` raises `HyDEUnavailableError`
rather than silently falling back to the original query or returning an
empty/degraded result disguised as success.
"""

from __future__ import annotations

from app.retrieval.errors import HyDEUnavailableError
from app.retrieval.interfaces import ExpansionResult, QueryExpander
from app.retrieval.llm_client import GenerationParams, LLMClient
from app.retrieval.prompts import render_hyde_prompt


class HyDEExpander(QueryExpander):
    def __init__(self, client: LLMClient, max_tokens: int, temperature: float) -> None:
        self._client = client
        self._max_tokens = max_tokens
        self._temperature = temperature

    def is_available(self) -> bool:
        return self._client.is_reachable()

    def expand(self, query: str) -> ExpansionResult:
        if not self.is_available():
            raise HyDEUnavailableError(
                f"HyDE backend (model={self._client.model_id}) is not reachable."
            )
        params = GenerationParams(max_tokens=self._max_tokens, temperature=self._temperature)
        prompt = render_hyde_prompt(query)
        try:
            generated = self._client.generate(prompt, params)
        except Exception as exc:  # noqa: BLE001
            raise HyDEUnavailableError(f"HyDE generation failed: {exc}") from exc

        if not generated.strip():
            raise HyDEUnavailableError("HyDE backend returned an empty passage.")

        return ExpansionResult(
            original_query=query,
            expanded_text=generated,
            model=self._client.model_id,
            generation_params={"max_tokens": self._max_tokens, "temperature": self._temperature},
        )
