# Phase 7 evaluation: reproducibility

A future researcher (or a grader) should be able to regenerate every
number in [`PHASE_7_EVALUATION_REPORT.md`](PHASE_7_EVALUATION_REPORT.md)
from this document alone.

## Environment

- Python: 3.12 (see `backend/.python-version`)
- Package manager: [`uv`](https://docs.astral.sh/uv/) (`backend/uv.lock` pins exact versions)
- OS this run was produced on: macOS (Darwin), Apple Silicon (arm64) — see
  `manifest.json`'s `platform` field in each run directory for the exact
  string. No GPU was used; all inference (BGE embeddings, cross-encoder
  reranking) ran on CPU.
- Working directory for all commands below: `backend/`

## Dependencies

All dependencies are declared in `backend/pyproject.toml` / locked in
`backend/uv.lock`. Phase 7 added: `pyyaml` (config loading), `matplotlib`
(figures), `scipy` (Wilcoxon signed-rank test). Install everything with:

```bash
cd backend
uv sync
```

## Model requirements

| Model | Used for | Available in this environment? |
|---|---|---|
| `BAAI/bge-small-en-v1.5` | Dense embeddings | Yes (cached under `~/.cache/huggingface`) |
| `cross-encoder/ms-marco-MiniLM-L-6-v2` | Reranking | Yes (cached) |
| `deepseek-r1:8b` (via Ollama) | Generation | **No** — `ollama` binary not installed |
| HyDE model (via Ollama) | Query expansion | **No** — same Ollama dependency |
| `llava-phi3` (via Ollama) | Image/diagram description | **No** — same Ollama dependency |
| `tesseract` | OCR | **No** — binary not installed |
| `faster-whisper` | Audio transcription | Library importable, but no real transcription was run for this dataset |

`backend/app/benchmarking/availability.py` performs these checks
programmatically and every run's `manifest.json` records the actual
result — this table is a snapshot of what that script found when this
report was written, not an assumption.

## Dataset preparation

The pilot dataset is checked into the repo already
(`evaluation/datasets/pilot_v1.json`). To regenerate it (only needed if
`backend/tests/fixtures/study_notes.*` changes):

```bash
cd backend
uv run python scripts/build_phase7_pilot_dataset.py
```

This re-runs real Phase 1 ingestion against the fixtures, verifies every
question's `gold_chunk_ids` actually exist in the resulting chunk set, and
overwrites `evaluation/datasets/pilot_v1.json`.

## Benchmark commands

**1. Baseline retrieval evaluation, ablations, chunking experiment, mocked-HyDE pipeline validation, and failure analysis:**

```bash
cd backend
uv run python scripts/run_phase7_benchmark.py --config ../evaluation/configs/baseline.yaml
```

Output: a new `evaluation/results/run_baseline_<timestamp>/` directory
containing `manifest.json`, `retrieval_results.json` (every config × top-k
× per-query metric), `retrieval_comparison.{md,csv}`, `chunking_
experiment.json`, `hyde_pipeline_validation.json`, `failures.json`, and
`summary.json`. Figures are written to `evaluation/figures/`.

**2. Baseline-vs-final comparison + statistical analysis + latency:**

```bash
cd backend
uv run python scripts/run_phase7_final_comparison.py ../evaluation/results/run_baseline_<timestamp>
```

(Point it at the exact run directory printed by step 1.) Output:
`baseline_vs_final.{md,csv}`, `statistical_analysis.json`, and
`latency_summary.json` written into that same run directory, plus a
comparison figure in `evaluation/figures/`.

**3. Unit tests (deterministic, no model downloads):**

```bash
cd backend
uv run pytest tests/benchmarking/
```

**4. Integration tests (real BGE/cross-encoder model loads — not run by default):**

```bash
cd backend
uv run pytest -m integration tests/benchmarking/
```

## Random seeds

`RunConfig.seed` (default 42, set in `evaluation/configs/*.yaml`) is
recorded in every run's `manifest.json`. It seeds
`app/benchmarking/statistics_.py`'s bootstrap resampling. BM25/BGE/
cross-encoder inference is deterministic given fixed model weights and
input text — no other randomness is introduced by the retrieval pipeline
itself.

## Configuration files

- [`evaluation/configs/baseline.yaml`](../../evaluation/configs/baseline.yaml) — Phase 7C/7F baseline run (existing/"C1" chunking).
- [`evaluation/configs/final_system.yaml`](../../evaluation/configs/final_system.yaml) — carries the same dataset/questions/metrics for a would-be re-run under a different chunking variant; see the evaluation report's "Evidence-Based Improvements" for why chunking was evaluated but not adopted, and reranking was recommended as the actual improvement without needing a separate re-run.

## Known unavailable dependencies (do not silently substitute)

Ollama, tesseract, and a real (non-mocked) transcription/VLM run are not
available in this environment. Every section of
`PHASE_7_EVALUATION_REPORT.md` that would depend on one of these states
`NOT MEASURED` / `NOT AVAILABLE` explicitly, with the reason, rather than
substituting a different model or a mocked result presented as real.

## Expected runtime

On the reference hardware (Apple Silicon Mac, CPU-only):

- `build_phase7_pilot_dataset.py`: a few seconds.
- `run_phase7_benchmark.py --config baseline.yaml`: approximately 30-60
  seconds (dominated by loading the BGE and cross-encoder models twice —
  once for the main retrieval sweep, once for the chunking experiment and
  again for failure analysis).
- `run_phase7_final_comparison.py`: a few seconds (reads existing JSON,
  no model inference).
- `pytest tests/benchmarking/` (unit only): under 5 seconds.
- `pytest -m integration tests/benchmarking/`: approximately 30-40
  seconds.

## Hardware assumptions

CPU-only. The corpus (23 chunks) and question set (14 questions) are
small enough that reported latency figures (see the evaluation report's
"Latency / Efficiency" section) are dominated by per-call Python/model
overhead, not corpus size — they should not be extrapolated to a
larger corpus or compared against GPU-backed numbers from elsewhere.
