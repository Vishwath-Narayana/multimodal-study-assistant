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
├── api/            FastAPI routers
├── core/           config, logging
├── models/         ORM/data models (Phase 1+)
├── schemas/        Pydantic request/response schemas (Phase 1+)
├── services/       cross-cutting application services
├── ingestion/       document parsing & chunking (Phase 1)
├── retrieval/       BM25 / FAISS / RRF / reranking (Phase 2)
├── generation/       prompt construction & LLM generation (Phase 3)
├── multimodal/       OCR / VLM / audio processing (Phase 5)
├── explainability/    citation validation & token grounding (Phase 4)
└── study/            quiz/MCQ/flashcard generation (Phase 6)
```

Most of these packages are currently empty placeholders — see
[docs/roadmap.md](../docs/roadmap.md).
