# Security Principles

Status: **design principles only** for Phase 0. No ingestion, retrieval, or
generation code exists yet to secure — this document establishes the
principles that later phases must follow, not a built security framework.

## Core Principle

**Retrieved document content is data, not instructions.** Text pulled from
a student's uploaded PDF, slide, image OCR, or transcript is never treated
as a system or developer instruction, regardless of what it contains or
claims (e.g. a document containing "ignore previous instructions and ...").

## Requirements for Later Phases

- **Prompt injection resistance**: prompt construction (Phase 3) must keep
  retrieved chunk text in a clearly delimited, non-instruction role, and the
  generation layer must not execute directives found inside retrieved text.
- **Document poisoning awareness**: a malicious or corrupted document should
  degrade gracefully (bad chunk, low relevance) rather than compromise the
  pipeline or other documents.
- **Provenance**: every chunk traces back to its source document and
  location (page/section/slide/timestamp) — see
  [docs/architecture/database.md](../architecture/database.md).
- **File hashing**: uploaded files are hashed on ingestion (`documents.file_hash`)
  for dedup and integrity tracking.
- **Safe prompt construction**: system instructions, user query, and
  retrieved evidence are kept in separate, clearly labeled sections of the
  prompt — never concatenated into a single untrusted blob.
- **Malicious document testing**: the test suite (Phase 3+) should include
  documents that attempt prompt injection, to verify the system does not
  follow embedded instructions.
- **Isolation of system instructions from retrieved text**: the system
  prompt is never derived from or modifiable by document content.

## Explicit Non-Goals for Now

- No authentication/authorization system (local-first, single user).
- No network-facing deployment hardening (not deployed yet).
- No elaborate sandboxing framework — principles above are applied directly
  in the ingestion/generation code as it is written, not via a separate
  security subsystem.
