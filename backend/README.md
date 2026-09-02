# Backend

FastAPI application for the AI-Powered Multimodal Study Assistant.

## Setup

```bash
uv sync --dev
```

## Run

```bash
uv run uvicorn app.main:app --reload
```

## Test / Lint / Type-check

```bash
uv run pytest
uv run ruff check .
uv run mypy app
```

## Structure

```
app/
├── api/            FastAPI routers (health, documents)
├── core/           config, logging
├── models/         ORM/data models (Phase 2+; ingestion currently persists via app/ingestion/repository.py)
├── schemas/        Pydantic request/response schemas
├── services/       cross-cutting application services (unused so far)
├── ingestion/       document parsing & chunking — implemented, Phase 1
├── retrieval/       BM25 / FAISS / RRF / reranking (Phase 2)
├── generation/       prompt construction & LLM generation (Phase 3)
├── multimodal/       OCR / VLM / audio processing (Phase 5)
├── explainability/    citation validation & token grounding (Phase 4)
└── study/            quiz/MCQ/flashcard generation (Phase 6)
```

`app/ingestion/` is the first non-trivial package — see
[docs/architecture/ingestion.md](../docs/architecture/ingestion.md) for its
design. Everything else beyond `api`/`core`/`ingestion` is still an empty
placeholder — see [docs/roadmap.md](../docs/roadmap.md).

## Regenerating test fixtures

`backend/tests/fixtures/` holds small, synthetic, deterministically
generated "study notes" documents (never real/copyrighted material) used
by the ingestion tests. Regenerate them with:

```bash
uv run python scripts/generate_fixtures.py
```
