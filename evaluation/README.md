# Evaluation

Evaluation datasets, benchmarks, metrics implementations, and experiment
configs/results for this project.

- `datasets/` — evaluation query/document sets (sample/mock data only;
  never real student documents)
- `benchmarks/` — fixed benchmark definitions used across experiments
- `metrics/` — metric implementations (retrieval, generation, grounding —
  see [docs/research/evaluation-plan.md](../docs/research/evaluation-plan.md))
- `experiments/` — per-run configuration + results

Populated starting in Phase 11 ("Phase 7 — Evaluation & Benchmarking" in
the implementation brief this work was built from — see
[docs/roadmap.md](../docs/roadmap.md) and
[docs/evaluation/PHASE_7_EVALUATION_REPORT.md](../docs/evaluation/PHASE_7_EVALUATION_REPORT.md)).
No results are ever fabricated or recorded here ahead of an actual run —
`configs/` and `datasets/` are curated inputs; `results/` and `figures/`
are generated output, committed as evidence for the numbers in the
report above (see `backend/scripts/run_phase7_benchmark.py`). `datasets/
pilot_v1.json` is built from the real Phase 1 test fixtures
(`backend/tests/fixtures/study_notes.*`), which are synthetic example
course material created for unit testing — never real student documents.
