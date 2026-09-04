# Reproducibility

This document records the environment and parameters needed to reproduce any
experiment run against this project. It is updated as components are
actually implemented — parameters listed as "baseline (planned)" are the
values we intend to use once that component exists, not results already
produced.

## Environment (Phase 0)

| Item | Value |
|---|---|
| OS assumption | macOS / Linux, local-first |
| Python version | 3.12 (pinned via `uv`, see `backend/.python-version`) |
| Node version | 22+ (pnpm 11 requires Node ≥22.13; developed against Node 26; CI pinned to Node 22) |
| Package managers | `uv` (backend), `pnpm` (frontend) |

## Ingestion Configuration (Phase 1, implemented)

| Parameter | Value | Source |
|---|---|---|
| Document parser | Docling (`docling` PyPI package) | EduRAG baseline |
| Chunk target size | 512 tokens (`CHUNK_TARGET_TOKENS`) | EduRAG baseline ("approximately 512 tokens") |
| Chunk overlap | 50 tokens (`CHUNK_OVERLAP_TOKENS`) | **Implementation choice** — not specified by the baseline paper |
| Token counting | whitespace-split word count | **Implementation choice** — not any specific embedding model's tokenizer; alignment deferred to Phase 2 |
| Document identity | SHA-256 of file bytes, used directly as `document_id` | **Implementation choice** |
| Max upload size | 50MB (`MAX_UPLOAD_SIZE_MB`) | **Implementation choice** |
| Supported formats | pdf, docx, pptx, html, htm (`SUPPORTED_EXTENSIONS`) | **Implementation choice** — EduRAG does not enumerate a fixed format list |
| Formula/equation enrichment | disabled (Docling `do_formula_enrichment=False`) | **Implementation choice** — avoids an additional VLM model download; see docs/architecture/ingestion.md §4 |

All of the above are read from `Settings` (`backend/app/core/config.py`),
overridable via `.env` — never hard-coded inside ingestion logic (PHASE 1
§27 of the project brief).

## Retrieval Configuration (Phase 2, implemented)

| Parameter | Value | Source |
|---|---|---|
| Embedding model | `BAAI/bge-small-en-v1.5` | EduRAG baseline |
| Embedding dimension | 384 | Fixed by the model |
| Embedding model revision | not pinned (published `main` revision used as-is) | **Implementation choice** — no local HF-revision-lock mechanism existed to add a pin against in this environment; see note below |
| Embedding metric / normalization | cosine similarity via inner product over L2-normalized vectors (`normalize_embeddings=True`) | Matches BGE's documented usage |
| FAISS index type | `IndexFlatIP` (exact search) | **Implementation choice** — spec explicitly avoids premature ANN optimization |
| BM25 library | `rank-bm25` (`BM25Okapi`) | **Implementation choice** (established library, not from scratch) |
| BM25 tokenization | lowercase + alphanumeric split, no stopwords, no stemming | **Implementation choice**, documented in `app/retrieval/tokenizer.py` |
| `BM25_TOP_K` | 20 | EduRAG baseline |
| `DENSE_TOP_K` | 20 | EduRAG baseline |
| `EMBEDDING_BATCH_SIZE` | 32 | **Implementation choice** |
| RRF k | 60 | EduRAG baseline (standard RRF constant) |
| `RRF_CANDIDATE_K` | 20 | EduRAG baseline (see docs/architecture/retrieval.md §12 citation caveat) |
| Reranker model | `cross-encoder/ms-marco-MiniLM-L-6-v2` | EduRAG baseline |
| `RERANK_CANDIDATE_K` | 20 | EduRAG baseline |
| `FINAL_TOP_K` | 5 | EduRAG baseline |
| HyDE model | `deepseek-r1:1.5b` via Ollama (`HYDE_MODEL`, `OLLAMA_BASE_URL`) | Preferred baseline model, project brief |
| HyDE enabled by default | `false` (opt-in via `HYDE_ENABLED`) | **Implementation choice** |
| HyDE generation params | `max_tokens=256`, `temperature=0.2` | **Implementation choice** |
| HyDE prompt | one centralized template, `app/retrieval/prompts.py` | **Implementation choice** (Gao et al.-style framing) |
| Random seed | none required — BM25/FAISS/RRF/reranking are deterministic given fixed inputs; HyDE generation (when a real LLM is used) is set to low temperature (0.2) rather than a fixed seed, since Ollama's `/api/generate` does not expose one for `deepseek-r1` in the version tested | **Implementation choice** |

**Embedding-model revision note**: `sentence-transformers` resolves
`BAAI/bge-small-en-v1.5` to whatever revision Hugging Face currently serves
as `main` for that repo; no commit-hash pin was added because doing so
would require vendoring/mirroring the model or adding a revision-lock
mechanism not otherwise needed by this project — flagged here rather than
silently treated as fully pinned.

## Generation Configuration (Phase 3, implemented)

| Parameter | Value | Source |
|---|---|---|
| Generation model | `deepseek-r1:8b` via Ollama (`LLM_MODEL`, replaceable) | Project brief's preferred research baseline |
| Generation temperature | 0.2 (`GENERATION_TEMPERATURE`) | **Implementation choice** — favors reproducibility over diversity; not mandated by EduRAG |
| Generation max tokens | 512 (`GENERATION_MAX_TOKENS`) | **Implementation choice** |
| Generation timeout | 120s (`GENERATION_TIMEOUT_SECONDS`) | **Implementation choice** |
| Random seed | none — Ollama's `/api/generate` does not expose one for `deepseek-r1` in the version tested; low temperature (0.2) is used instead, same as HyDE | **Implementation choice** |
| Citation format | `[chunk:<chunk_id>]`, extracted via a fixed regex | **Implementation choice** — see docs/architecture/generation.md |
| Attribution weighting | 0.7 x cross-encoder relevance + 0.3 x lexical overlap (`ATTRIBUTION_RELEVANCE_WEIGHT`/`ATTRIBUTION_LEXICAL_WEIGHT`) | EduRAG baseline |
| Token grounding tiers | exact 1.0 / stem 0.9 / substring 0.8 / ungrounded 0.2 | EduRAG baseline (fixed, not configurable) |
| Grounding "grounded" cutoff | 0.8 (`GROUNDING_THRESHOLD`) | **Implementation choice** |
| Evidence sufficiency thresholds | min chunks 1, min lexical overlap 0.08, min reranker score 0.0 (`SUFFICIENCY_MIN_*`) | **Implementation choice**, not scientifically validated |
| Contradiction topic-overlap threshold | 0.2 (`CONTRADICTION_TOPIC_OVERLAP_THRESHOLD`) | **Implementation choice** |

All of the above are read from `Settings`, overridable via `.env` — see
`.env.example` and [docs/architecture/generation.md](../architecture/generation.md)
for the full design and documented limitations of each heuristic.

## Multimodal Configuration (Phase 4, implemented)

| Parameter | Value | Source |
|---|---|---|
| VLM provider | none by default (`VLM_PROVIDER=""`) | **Implementation choice** — optional, see docs/architecture/multimodal.md |
| VLM model (when enabled) | Ollama-served LLaVA/LLaVA-Phi3-family model (`VLM_MODEL`) | Project brief's preferred choice |
| VLM generation params | `max_tokens=300` (`VLM_MAX_TOKENS`), `temperature=0.2` (fixed), timeout 60s (`VLM_TIMEOUT_SECONDS`) | **Implementation choice** |
| OCR provider | none by default (`OCR_PROVIDER=""`) | **Implementation choice** — optional |
| OCR engine (when enabled) | `tesseract` via `pytesseract` (`OCR_PROVIDER=tesseract`) | **Implementation choice** |
| Transcription provider | none by default (`TRANSCRIPTION_PROVIDER=""`) | **Implementation choice** — optional |
| Whisper model (when enabled) | `base` (`WHISPER_MODEL`), via `faster-whisper` | **Implementation choice** |
| Whisper device/compute type | `auto` / `int8` (`WHISPER_DEVICE`/`WHISPER_COMPUTE_TYPE`) | **Implementation choice** — CPU-compatible, no GPU required |
| Whisper language | auto-detect by default (`WHISPER_LANGUAGE=""`) | **Implementation choice** |
| Audio formats | wav, mp3, m4a (`AUDIO_SUPPORTED_EXTENSIONS`) | **Implementation choice** |
| Max audio upload size | 200MB (`MAX_AUDIO_UPLOAD_SIZE_MB`) | **Implementation choice** |
| Transcript chunk token budget | 512 (`TRANSCRIPT_CHUNK_TARGET_TOKENS`), no overlap | **Implementation choice** — see docs/architecture/multimodal.md "Timestamp-Aware Chunking" |
| Image artifact size cap | 20MB (`MAX_IMAGE_ARTIFACT_SIZE_MB`) | **Implementation choice** |
| Image artifact pixel cap | 40,000,000 (`MAX_IMAGE_PIXELS`) | **Implementation choice** — decompression-bomb guard |

All of the above are read from `Settings`, overridable via `.env` — see
`.env.example` and
[docs/architecture/multimodal.md](../architecture/multimodal.md).

## Study Engine Configuration (Phase 5, implemented)

| Parameter | Value | Source |
|---|---|---|
| LLM provider/model | reuses `LLM_PROVIDER`/`LLM_MODEL` (Phase 3) | **Implementation choice** — no separate study-engine provider concept |
| Generation params | `max_tokens=1024` (`STUDY_MAX_TOKENS`), `temperature=0.2` (`STUDY_TEMPERATURE`), timeout 120s (`STUDY_TIMEOUT_SECONDS`) | **Implementation choice** — larger `max_tokens` than chat's 512 since quiz/mcq/flashcards JSON can hold several items |
| Requested item count bounds | `[1, 20]` (`STUDY_MIN_COUNT`/`STUDY_MAX_COUNT`) | **Implementation choice**, not EduRAG-specified |
| Sufficiency / citation validation / contradiction checking | reuses Phase 3's `SUFFICIENCY_*`/`CONTRADICTION_TOPIC_OVERLAP_THRESHOLD` settings unchanged | No new thresholds introduced for Phase 5 |

Retrieval mode/top_k/study mode/difficulty/requested count/prompt version
(there is exactly one prompt per mode, versioned implicitly by the git
commit of `app.study.prompts`) are all request parameters, not fixed
config — see [docs/API.md](../API.md) for exact request shapes.

## Known Environment Dependency (Phase 4)

No VLM (`llava`-family), OCR (`tesseract` binary), or Whisper model was
available/installed in this environment while implementing this phase.
All three are implemented as optional, configuration-driven providers
(`VLM_PROVIDER`/`OCR_PROVIDER`/`TRANSCRIPTION_PROVIDER` empty by default)
with deterministic fake providers used by the default test suite
(`tests/multimodal/fakes.py`) and no test in that suite requires any of
the three real dependencies — `requires_tesseract`/`requires_whisper`
pytest markers exist for future opt-in real-model tests, following the
same pattern as `requires_ollama`/`requires_model`. `faster-whisper` and
`pytesseract` are installed as regular dependencies (no torch, CPU-only),
but the `tesseract` system binary and Whisper model weights are only
fetched/required on first real use.

The Phase 4 dev dataset
(`backend/app/multimodal/evaluation/dataset.json`, 8 queries) was built
with **mocked** VLM/OCR/transcription providers
(`backend/scripts/build_multimodal_eval_dataset.py`), the same "prove the
pipeline is wired end to end, not a real-model measurement" precedent as
the Phase 2 mocked-HyDE benchmark — see
[docs/research/evaluation-plan.md](evaluation-plan.md) "Multimodal
Metrics".

## Known Environment Dependency (Phase 1)

Docling's default PDF pipeline downloads ML layout-detection and RapidOCR
model weights from Hugging Face / ModelScope on first use (a few tens of
MB, cached under the Python environment afterward). Running PDF ingestion
for the first time — including running the backend test suite for the
first time — requires network access. DOCX/PPTX/HTML parsing use
format-native Docling backends and do not require any model download.

## Known Environment Dependency (Phase 2)

`BAAI/bge-small-en-v1.5` (~130MB) and `cross-encoder/ms-marco-MiniLM-L-6-v2`
(~90MB) are downloaded from Hugging Face on first real use (cached under
the sentence-transformers cache directory afterward). The default backend
test suite (`uv run pytest`) does **not** trigger this — it uses a
deterministic fake embedding provider and a mocked cross-encoder (see
`tests/retrieval/fakes.py`) and is excluded-by-default from any test
marked `requires_model`/`integration`/`requires_ollama` (see
`pyproject.toml`'s `addopts`). Running
`backend/scripts/run_retrieval_experiment.py` or building a real FAISS
index via the `POST /retrieval/search` API does trigger these downloads.
HyDE additionally requires a locally running Ollama server serving
`deepseek-r1:1.5b` (or the configured `HYDE_MODEL`) — CI does not run
Ollama, and no test in the default suite requires it.

## Known Environment Dependency (Phase 3)

Real generation requires a locally running Ollama server serving
`deepseek-r1:8b` (or the configured `LLM_MODEL`) — CI does not run Ollama,
and no test in the default suite (`uv run pytest`) requires it. The default
suite uses `FakeGenerator`/`FakeLLMClient`
(`tests/generation/fakes.py`); the one real-Ollama test
(`tests/generation/test_generator_integration.py`) is marked
`requires_ollama` and self-skips when Ollama/the model isn't reachable.
`backend/scripts/run_generation_experiment.py` uses a mocked generator by
default and only attempts a real Ollama call when passed `--ollama`.

## Dataset Versions

The Phase 2 dev benchmark (`backend/app/retrieval/evaluation/dataset.json`,
6 queries, categories: factual/definition/table-related/section-specific/
multi-document) is built directly against Phase 1's test fixtures
(`backend/tests/fixtures/study_notes.{html,docx,pptx}`), which are
synthetic and generated deterministically by
`backend/scripts/generate_fixtures.py`. Chunk ids referenced as
`relevant_chunk_ids` were derived by actually running Phase 1 ingestion +
chunking against those fixtures (`backend/scripts/build_eval_dataset.py`),
not hand-typed — they are stable as long as the fixture files' byte
content does not change (`document_id` is a SHA-256 hash of the file).
This is a small dev benchmark for exercising and comparing retrieval
modes during development, not a final evaluation dataset.

The Phase 4 multimodal dev dataset
(`backend/app/multimodal/evaluation/dataset.json`) is built the same way:
directly against `study_notes.docx` (real Docling parsing/chunking) plus a
synthetic silent WAV, with chunk ids derived by actually running ingestion
(`backend/scripts/build_multimodal_eval_dataset.py`) rather than
hand-typed. Its image/transcript categories used mocked VLM/OCR/
transcription providers (no real model available in this environment) —
labeled as such in the dataset's own `description` field. Its `equation`
category is intentionally left unpopulated (no fixture produces a real
`EQUATION` chunk, since Docling formula enrichment stays disabled) rather
than fabricated.

## Experiment Configuration Policy

Every experiment must be run from an explicit, checked-in configuration
(not parameters buried in source code) so it can be rerun later with the
same settings. `backend/scripts/run_retrieval_experiment.py` is that
configuration for the Phase 2 retrieval benchmark; it writes a full report
(config, timestamp, model identifiers, per-query results, aggregate
metrics, latency) to `backend/experiment-results/` (gitignored — reports
are regenerated by re-running the script, not committed as static files).

**Actual run performed for this phase** (2026-09-02, this environment):
real `rank-bm25`, real `BAAI/bge-small-en-v1.5` + `IndexFlatIP` FAISS, real
`cross-encoder/ms-marco-MiniLM-L-6-v2` reranker; HyDE used a **mocked**
`QueryExpander` (a fixed canned passage) because no local Ollama server was
available in this environment — recorded in the report's `config` block as
`"hyde_mocked": true`, never presented as a real HyDE run. See
[docs/research/evaluation-plan.md](evaluation-plan.md) for the resulting
numbers and their caveats.

No experimental results are recorded in this document, or anywhere else in
the repository, until the corresponding run has actually been executed.

**Phase 3**: no generation-ablation experiment run has been executed in
this environment yet (no locally reachable Ollama server was available
while implementing this phase), so no `run_generation_experiment.py`
results are recorded here. See
[docs/architecture/generation.md](../architecture/generation.md)
"Evaluation" for what the script measures and why the current dev dataset
cannot yet support Token F1/ROUGE-L/BERTScore.
