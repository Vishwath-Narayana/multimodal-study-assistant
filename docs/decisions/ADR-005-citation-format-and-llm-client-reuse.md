# ADR-005: Citation Format and LLM Client Reuse

## Status
Accepted

## Context
Phase 3 needed (a) a way for the LLM to cite retrieved chunks that is
mechanically parseable and safe to validate deterministically, and (b) a
generation-time LLM client. Phase 2 already added `LLMClient`/`OllamaClient`
(`app/retrieval/llm_client.py`) for HyDE, described in its own docstring as
"the only place HTTP calls to the LLM backend happen."

## Decision

**Citation format**: the model is instructed to cite using the literal
token `[chunk:<chunk_id>]` immediately after the claim it supports.
Extraction is a single fixed regex
(`app/generation/citations.py::extract_citations`); an answer that cites in
any other shape yields zero extracted citations rather than a best-effort
parse. Alternatives considered:
- Free-form citation (e.g. "(see Section 2)") — not mechanically
  verifiable against a chunk_id, would require fuzzy matching.
- A numbered reference list (`[1]`, `[2]`, ...) resolved via a separate
  index — adds an indirection layer for no benefit here, since chunk_ids
  are already short, stable strings.

**LLM client reuse**: `app/generation/generator.py::OllamaGenerator` builds
on the existing `LLMClient`/`OllamaClient` rather than adding a second HTTP
client. It was already generic (prompt in, text out, model-agnostic) with
no HyDE-specific assumptions baked in — duplicating it would have violated
ADR-004's "swap without touching calling code" goal by creating two clients
that could drift apart. `GenerationParams` (`max_tokens`, `temperature`) is
reused unchanged for the same reason.

## Consequences
- Citation validation (`DeterministicCitationValidator`) is a pure lookup
  against the retrieved evidence set — no NLP, no fuzzy matching, fully
  deterministic and unit-testable with hand-written examples.
- A model that doesn't follow the exact citation format produces an answer
  with zero valid citations, which is visible in the response
  (`citations: []`) rather than silently treated as fully grounded.
- `app/retrieval/llm_client.py`'s docstring claim ("the only place HTTP
  calls to the LLM backend happen") remains true after Phase 3 — HyDE and
  generation share one client module, one `OllamaClient` implementation.
- If a future phase needs streaming, stop sequences, or multi-turn chat,
  `LLMClient` will need to grow (or a second, explicitly-scoped interface
  will need to be added) — Phase 3 did not need any of those and did not
  add them speculatively.
