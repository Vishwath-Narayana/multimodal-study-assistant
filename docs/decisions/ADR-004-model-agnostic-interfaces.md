# ADR-004: Model-Agnostic Component Interfaces

## Status
Accepted

## Context
This project's core value is comparing configurations (ablation study,
README §7, [docs/research/ablation-plan.md](../research/ablation-plan.md)):
BM25 only vs. FAISS only vs. hybrid, with/without HyDE, with/without
reranking, baseline vs. baseline+extensions. Embedding models, rerankers,
LLM backends, and VLM backends are all likely to change during
experimentation, and possibly need to be swapped again after publication.

## Decision
Every major pipeline component is implemented behind a small interface so
implementations can be swapped without touching calling code, e.g.:

```
Retriever
├── BM25Retriever
└── DenseRetriever

Fusion
└── RRFFusion

Reranker
└── CrossEncoderReranker

Generator
└── LLMGenerator
```

Concrete model names/versions are configuration (`.env`, experiment
config), never hard-coded inside component logic.

## Consequences
- Ablation runs can swap one component at a time without duplicating
  pipeline code.
- Slightly more upfront structure (interfaces + implementations) than
  writing one monolithic pipeline function — justified here because
  swapping components is a core requirement, not a hypothetical.
- Interfaces are added only for components that are actually expected to
  vary across experiments — not applied reflexively to every class in the
  codebase.
