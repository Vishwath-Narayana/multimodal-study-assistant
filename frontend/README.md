# Frontend

React + TypeScript + Tailwind CSS application shell for the AI-Powered
Multimodal Study Assistant.

## Setup

```bash
pnpm install
```

## Run

```bash
pnpm dev
```

## Build / Lint

```bash
pnpm run build
pnpm run lint
```

## Structure

```
src/
├── components/   AppShell, UploadPlaceholder, ChatPlaceholder
├── pages/         StudyPage
├── styles/        Tailwind entrypoint + design tokens
├── App.tsx
└── main.tsx
```

This is currently a minimal shell (navigation, upload placeholder, chat
placeholder) — see [docs/roadmap.md](../docs/roadmap.md) for when the real
upload/chat/study screens are built (Phase 10).
