"""Phase 7F.2 chunking ablation: C1 (existing whitespace-approximate
token count) vs. C2 (real BGE subword token count).

Documented existing issue (Phase 2 investigation, `docs/architecture/
ingestion.md`): `approx_token_count` splits on whitespace, but BGE's
subword tokenizer can produce meaningfully more tokens per word for
punctuation-heavy or unusual text, so a whitespace-512-word chunk can
approach or exceed the embedding model's real token budget. C2 measures
whether counting real BGE tokens while packing chunks changes retrieval
quality, using `ChunkingConfig.token_counter` (see `app/ingestion/
chunking.py`) rather than changing the default chunking behaviour.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.ingestion.chunking import ChunkingConfig, approx_token_count

if TYPE_CHECKING:
    from transformers import PreTrainedTokenizerBase

_tokenizer_cache: PreTrainedTokenizerBase | None = None


def _bge_tokenizer() -> PreTrainedTokenizerBase:
    global _tokenizer_cache
    if _tokenizer_cache is None:
        from transformers import AutoTokenizer

        _tokenizer_cache = AutoTokenizer.from_pretrained("BAAI/bge-small-en-v1.5")
    return _tokenizer_cache


def bge_token_count(text: str) -> int:
    """Real BGE subword token count, including special tokens (matches
    what actually gets truncated/fed to the model at embedding time)."""
    if not text:
        return 0
    return len(_bge_tokenizer().encode(text))


def baseline_chunking_config(target_tokens: int = 512, overlap_tokens: int = 50) -> ChunkingConfig:
    """C1 — existing behaviour, unchanged."""
    return ChunkingConfig(target_tokens=target_tokens, overlap_tokens=overlap_tokens)


def bge_aware_chunking_config(target_tokens: int = 512, overlap_tokens: int = 50) -> ChunkingConfig:
    """C2 — packs chunks by real BGE token count instead of whitespace
    words, so a chunk's `token_count` matches what the embedding model
    will actually see."""
    return ChunkingConfig(
        target_tokens=target_tokens, overlap_tokens=overlap_tokens, token_counter=bge_token_count
    )


def token_inflation_ratio(text: str) -> float:
    """BGE tokens per whitespace word — >1.0 means the whitespace
    approximation under-counts real tokens for this text."""
    words = approx_token_count(text)
    if words == 0:
        return 0.0
    return bge_token_count(text) / words
