# Security Principles

Status: these principles were **design-only through Phase 2**. As of
**Phase 3**, retrieved document content reaches an LLM prompt for the first
time in this project (`app/generation/prompts.py`) — see
[docs/architecture/generation.md](../architecture/generation.md)
"Security" for how the requirements below are applied, and their
documented limitations. Phases 5+ (multimodal, study engine, frontend,
deployment) still have no built security framework beyond what this
document already establishes.

## Core Principle

**Retrieved document content is data, not instructions.** Text pulled from
a student's uploaded PDF, slide, image OCR, or transcript is never treated
as a system or developer instruction, regardless of what it contains or
claims (e.g. a document containing "ignore previous instructions and ...").

## Requirements — Status

- **Prompt injection resistance** — *implemented, partial*: prompt
  construction (`app.generation.prompts.render_grounded_prompt`) keeps
  retrieved chunk text in a clearly delimited, labeled-as-data section, and
  the system instructions explicitly tell the model to treat directive-
  shaped text inside evidence as data, not instructions. This reduces risk
  but does not guarantee a model will always comply — see
  docs/architecture/generation.md "Limitations".
- **Document poisoning awareness** — *unchanged from Phase 1/2*: a
  malicious or corrupted document still degrades gracefully (bad chunk, low
  relevance/attribution score) rather than compromising the pipeline;
  Phase 3 adds no new document-poisoning-specific handling beyond citation
  validation rejecting any chunk_id not in the retrieved set.
- **Provenance**: every chunk traces back to its source document and
  location (page/section/slide/timestamp) — see
  [docs/architecture/database.md](../architecture/database.md). Phase 3's
  citations and evidence items carry this same provenance through to the
  `/chat/query` response.
- **File hashing**: uploaded files are hashed on ingestion (`documents.file_hash`)
  for dedup and integrity tracking.
- **Safe prompt construction** — *implemented*: system instructions, the
  student's question, and retrieved evidence are kept in three separate,
  clearly labeled sections of the prompt — never concatenated into a single
  untrusted blob.
- **Malicious document testing** — *implemented*:
  `tests/generation/test_security.py` verifies injected-instruction-shaped
  text in evidence stays confined to the evidence section of the rendered
  prompt, and that a citation such text tries to plant is still rejected by
  deterministic validation.
- **Isolation of system instructions from retrieved text** — *implemented*:
  the system prompt (`app.generation.prompts.SYSTEM_INSTRUCTIONS`) is a
  fixed constant, never derived from or modifiable by document content.

## Explicit Non-Goals for Now

- No authentication/authorization system (local-first, single user).
- No network-facing deployment hardening (not deployed yet).
- No elaborate sandboxing framework — principles above are applied directly
  in the ingestion/generation code as it is written, not via a separate
  security subsystem.
