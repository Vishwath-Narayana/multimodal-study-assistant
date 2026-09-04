# Frontend

React + TypeScript + Vite + Tailwind CSS student-facing application for
the AI-Powered Multimodal Study Assistant — see
[docs/architecture/frontend.md](../docs/architecture/frontend.md) for the
full design.

## Setup

```bash
pnpm install
```

Set `VITE_API_BASE_URL` in a `.env` file if the backend isn't at the
default `http://localhost:8000`.

## Run

```bash
pnpm dev
```

Requires the backend running (`cd ../backend && uv run uvicorn
app.main:app --reload`).

## Build / Lint / Test

```bash
pnpm run build
pnpm run lint
pnpm test
```

## Structure

```
src/
├── components/
│   ├── layout/      AppShell (navigation)
│   ├── common/       Loading/Error/Empty/InsufficientEvidence states
│   ├── documents/     UploadZone, DocumentList, StatusBadge
│   ├── evidence/      SourceCard, EvidencePanel, ArtifactImage — shared
│   │                  citation/evidence UI used by chat and study
│   ├── chat/          ChatMessage (user/assistant bubbles)
│   └── study/         GenerativePanel, GenerationControls, QuizRunner,
│                      MCQRunner, FlashcardDeck, DocumentScopeSelect
├── hooks/            useDocuments
├── lib/api/           Typed API client (client.ts, documents.ts,
│                      chunks.ts, chat.ts, study.ts, types.ts)
├── pages/             DashboardPage, LibraryPage, DocumentPage, ChatPage,
│                      StudyPage + pages/study/*Tab.tsx
├── styles/            Tailwind entrypoint + design tokens
├── App.tsx            Routes
└── main.tsx
```

## Environment

| Variable | Default | Purpose |
|---|---|---|
| `VITE_API_BASE_URL` | `http://localhost:8000` | Backend base URL |

## Known limitations

See [docs/architecture/frontend.md](../docs/architecture/frontend.md)
"Known limitations" — no conversation memory, no document-scoped chat (a
backend limitation), no study-history view (no backend endpoint for it).
