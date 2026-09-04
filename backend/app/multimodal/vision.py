"""`VisionProvider` implementations.

`OllamaVisionProvider` targets a local Ollama server serving a multimodal
model (LLaVA / LLaVA-Phi3 — spec section 8's preferred choice), reusing the
same `Settings.ollama_base_url` the HyDE/generation Ollama clients already
target rather than introducing a second LLM backend concept. It is a
*separate* client from `app.retrieval.llm_client.OllamaClient` because
Ollama's `/api/generate` takes an `images` field this project's text-only
`LLMClient` interface has no notion of.

`NullVisionProvider` is the default when `Settings.vlm_provider` is empty
(spec section 8: "must be optional") — always reports unavailable, never
called by the default test suite or CI.
"""

from __future__ import annotations

import base64
from pathlib import Path

import httpx

from app.ingestion.models import VisionStatus
from app.multimodal.interfaces import VisionProvider
from app.multimodal.models import VisionDescription
from app.multimodal.prompts import render_vision_prompt


class NullVisionProvider(VisionProvider):
    """Used when no VLM is configured. Never fabricates a description."""

    def describe(self, image_path: Path, *, context: str = "") -> VisionDescription:
        return VisionDescription(status=VisionStatus.UNAVAILABLE, description=None, model=None)

    def is_available(self) -> bool:
        return False

    @property
    def model_id(self) -> str:
        return ""


class OllamaVisionProvider(VisionProvider):
    def __init__(
        self,
        base_url: str,
        model: str,
        *,
        max_tokens: int = 300,
        timeout_seconds: float = 60.0,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._max_tokens = max_tokens
        self._timeout = timeout_seconds

    @property
    def model_id(self) -> str:
        return self._model

    def is_available(self) -> bool:
        try:
            response = httpx.get(f"{self._base_url}/api/tags", timeout=5.0)
            return response.status_code == 200
        except httpx.HTTPError:
            return False

    def describe(self, image_path: Path, *, context: str = "") -> VisionDescription:
        try:
            image_b64 = base64.b64encode(image_path.read_bytes()).decode("ascii")
        except OSError:
            return VisionDescription(
                status=VisionStatus.FAILED, description=None, model=self._model
            )

        try:
            response = httpx.post(
                f"{self._base_url}/api/generate",
                json={
                    "model": self._model,
                    "prompt": render_vision_prompt(context),
                    "images": [image_b64],
                    "stream": False,
                    "options": {"temperature": 0.2, "num_predict": self._max_tokens},
                },
                timeout=self._timeout,
            )
            response.raise_for_status()
            text = str(response.json().get("response", "")).strip()
        except (httpx.HTTPError, ValueError):
            return VisionDescription(
                status=VisionStatus.FAILED, description=None, model=self._model
            )

        if not text:
            return VisionDescription(
                status=VisionStatus.FAILED, description=None, model=self._model
            )
        return VisionDescription(status=VisionStatus.AVAILABLE, description=text, model=self._model)
