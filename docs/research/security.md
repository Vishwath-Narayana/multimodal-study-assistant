# Security Principles

Status: these principles were **design-only through Phase 2**. As of
**Phase 3**, retrieved document content reaches an LLM prompt for the first
time in this project (`app/generation/prompts.py`) — see
[docs/architecture/generation.md](../architecture/generation.md)
"Security" for how the requirements below are applied, and their
documented limitations. **Phase 4** extends untrusted-input validation to
image artifacts (decompression-bomb/oversized-file guards) and audio
uploads (magic-byte sniffing on top of the existing extension/size checks)
— see [docs/architecture/multimodal.md](../architecture/multimodal.md)
"Security". OCR text and VLM descriptions are treated as data through the
same existing evidence-is-data prompt framing; no new prompt path was
added for them. Phases 6+ (study engine, frontend, deployment) still have
no built security framework beyond what this document already
establishes.

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

## Phase 4 Additions

- **Image artifact validation** — *implemented*:
  `app.multimodal.security.validate_image_artifact` caps artifact file
  size and sets Pillow's `MAX_IMAGE_PIXELS` before opening a file
  (decompression-bomb guard), applied before OCR/VLM processing.
- **Audio upload validation** — *implemented*:
  `app.multimodal.security.validate_audio_upload` mirrors
  `app.ingestion.validation.validate_upload`'s extension/size checks, plus
  a magic-byte sniff (RIFF/WAVE, MP3 sync/ID3, MP4 `ftyp`) so a file
  claiming an audio extension but containing arbitrary bytes is rejected
  before reaching a transcription model.
- **OCR/VLM/transcript text as data** — *implemented, unchanged prompt
  path*: OCR text and VLM descriptions become part of `Chunk.content`
  exactly like any other chunk, and only reach an LLM prompt through the
  existing `render_grounded_prompt` evidence-is-data framing — no new
  prompt construction path was introduced for multimodal content.
- **Filename/path safety** — *reused, not duplicated*: audio storage uses
  the same `app.ingestion.storage.sanitize_filename`/`DataPaths`
  path-escape checks as document uploads.
- **Model-generated content caveat**: VLM output can be inaccurate or,
  like any LLM output, could in principle attempt to embed
  instruction-like text; it is subject to the same "data, not
  instructions" treatment as document content — no VLM-specific
  mitigation beyond that was added, since the existing prompt framing
  already applies to it uniformly.

## Explicit Non-Goals for Now

- No authentication/authorization system (local-first, single user).
- No network-facing deployment hardening (not deployed yet).
- No elaborate sandboxing framework — principles above are applied directly
  in the ingestion/generation code as it is written, not via a separate
  security subsystem.
