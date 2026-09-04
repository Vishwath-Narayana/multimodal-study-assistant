# Phase 7 pilot benchmark dataset (`pilot_v1`)

## Summary

| | |
|---|---|
| Dataset id | `pilot_v1` |
| Documents | 3 (same content, 3 source formats: `.html`, `.docx`, `.pptx`) |
| Subject areas | 1 (cell biology: photosynthesis, cellular respiration) |
| Chunks (real, ingested) | 23 total (html: 9, docx: 8, pptx: 6), including section-header parent chunks; 15 content chunks if parent headers are excluded |
| Questions | 14 |
| Answerable | 12 |
| Unanswerable | 2 |
| File | [`evaluation/datasets/pilot_v1.json`](../../evaluation/datasets/pilot_v1.json) |
| Build script | [`backend/scripts/build_phase7_pilot_dataset.py`](../../backend/scripts/build_phase7_pilot_dataset.py) |

## Why this dataset is small (read this before citing question counts)

Phase 7B's target was 5-10 subject areas and 50-500 questions. Before any
Phase 7 work began, this environment was checked for a real academic
corpus and found to have none: `data/raw/` contained only a placeholder
`.gitkeep` file (see git history on `feature/evaluation-benchmarking`).
The only real document content available anywhere in the repository is
the Phase 1 fixture set (`backend/tests/fixtures/study_notes.{html,docx,
pptx}`) — a single cell-biology topic used for Phase 1-2 unit tests, not
"student-owned academic material" as Phase 7B originally specified.

Given that constraint, the choice was between (a) fabricating a
larger/more diverse dataset, which the Phase 7 brief's absolute rule
explicitly forbids, or (b) building a genuine but small pilot from the one
real corpus available, and documenting the limitation honestly. Option (b)
was chosen. **This is a 7B-1 pilot only** — the dataset scale/subject
targets in the original brief were not met, and should not be read as met.
Expanding to 7B-2/7B-3 scale requires real multi-subject academic material
being added to `data/raw/`, at which point `build_phase7_pilot_dataset.py`
can be extended (or a new dataset built alongside it) following the same
discipline: chunk ids derived by actually running ingestion, gold evidence
verified by inspecting the real chunk content, not invented.

## Question categories

| Category | Count | Notes |
|---|---|---|
| factual | 3 | |
| definition | 1 | |
| table | 2 | Real table chunks (real Docling table extraction), not synthetic |
| cross_document | 1 | Same content across html/docx/pptx — tests consistency across parser outputs, not independent sources |
| multi_hop | 1 | Requires combining the organelle/function table with the photosynthesis paragraph |
| comparison | 1 | Spans the photosynthesis and cellular-respiration sections |
| explanation | 2 | |
| image | 1 | Retrieval-only (see below) |
| unanswerable | 2 | Tests abstention behavior |

Categories from the Phase 7B.1 brief **not populated**, and why:

- **contradictory** — the pilot corpus contains no genuinely conflicting
  statements. Constructing a fake contradiction to fill this category
  would violate the no-fabrication rule ("Do NOT force a single answer
  when the source material genuinely conflicts" cuts both ways: it also
  means not inventing a conflict that doesn't exist).
- **ambiguous** — same reasoning; a deliberately vague question with no
  real intended resolution in this corpus would be a fabricated test
  case, not a real one.
- **equation** — Docling formula enrichment is disabled by a Phase 1
  decision (`docs/architecture/ingestion.md`), so no fixture produces a
  real `EQUATION` chunk to write a question against.
- **transcript** (as a *real*, non-mocked category) — no real Whisper
  transcription is available in this environment (`faster_whisper` is
  importable but no audio ingestion with a real transcription provider
  was run for this dataset). Phase 4's own mocked-transcript fixture
  exists only to validate pipeline wiring, not as gold-standard benchmark
  content, and was not reused here as if it were.

## Modalities

| Modality | Count |
|---|---|
| text | 10 |
| table | 3 |
| image | 1 |

The single `image` question (`p011`, "What does the plant cell diagram
show?") is **retrieval-only**: no VLM is available in this environment
(see `docs/evaluation/PHASE_7_EVALUATION_REPORT.md` "Multimodal Results"),
so the question checks whether the correct image/caption chunk is
retrieved, not whether a generated description of the image is correct.
Its `gold_answer` is intentionally left unset rather than fabricated.

## Gold evidence methodology

Chunk ids are **never hand-typed**. `build_phase7_pilot_dataset.py` runs
the real Phase 1 ingestion pipeline (`DoclingParser` + `chunk_document`)
against the actual fixture bytes, producing the same content-hash-derived
chunk ids the production ingestion path would produce, then the script
validates that every `gold_chunk_ids` entry in every hand-curated question
actually exists in that real output before writing `pilot_v1.json` — a
question referencing a chunk id that ingestion didn't actually produce
fails the build. Query text, category assignment, and relevance judgments
were written by hand by inspecting the real parsed section text (see the
script's docstring for the extracted text this was based on).

## Answer annotation

For answerable questions, `gold_answer` is a short reference answer and
`acceptable_answers` lists alternative phrasings/keywords a semantic-match
grader could accept — exact string equality is never required (Phase 7B.1
requirement). No generation model produced these answers; they were
written by hand from the source text, since Phase 7 has no working
generation model in this environment to derive them from (see
"Generation Results: NOT MEASURED" in the evaluation report).

## Unanswerable-question construction

Both unanswerable questions (`p013`, `p014`) ask about topics genuinely
absent from the corpus (nitrogen fixation; mitochondrial DNA extraction
safety) — verified by inspecting the full parsed text of all three
documents, not merely assumed. `gold_chunk_ids` is `[]` and `answerable`
is `false`. These test retrieval/abstention behavior; see the evaluation
report's "Evidence Sufficiency / Abstention" section for why the
abstention *decision* itself (which requires generation) is NOT MEASURED,
while retrieval behavior on these questions is discussed under
"Limitations."

## Contradictory-question construction

Not constructed — see "Question categories" above.

## Dataset limitations (verbatim from `pilot_v1.json`)

The dataset file itself carries this same limitations list in its
`limitations` field, so it travels with the data:

- Single subject area (cell biology) — the 5-10 subject area target was
  not met; no other real academic material was available.
- contradictory-source and ambiguous-query categories are not populated.
- equation category is not populated (formula enrichment disabled).
- transcript category is not populated with real audio content.
- The image question is retrieval-only (no VLM available).

## Privacy

All content in this dataset originates from `backend/tests/fixtures/`,
which is synthetic example course material created for Phase 1 unit
testing, not real student work — there is no private/student-sensitive
content in this dataset or in this document.
