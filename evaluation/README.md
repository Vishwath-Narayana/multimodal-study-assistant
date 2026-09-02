# Evaluation

Evaluation datasets, benchmarks, metrics implementations, and experiment
configs/results for this project.

- `datasets/` — evaluation query/document sets (sample/mock data only;
  never real student documents)
- `benchmarks/` — fixed benchmark definitions used across experiments
- `metrics/` — metric implementations (retrieval, generation, grounding —
  see [docs/research/evaluation-plan.md](../docs/research/evaluation-plan.md))
- `experiments/` — per-run configuration + results

This directory is currently empty (Phase 0). It is populated starting in
Phase 11 per [docs/roadmap.md](../docs/roadmap.md), once retrieval and
generation exist to evaluate. No results are ever fabricated or recorded
here ahead of an actual run.
