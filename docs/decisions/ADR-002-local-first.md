# ADR-002: Local-First Architecture

## Status
Accepted

## Context
This is a research/academic project focused on RAG architecture,
explainability, and evaluation quality — not on serving many concurrent
users or operating at scale.

## Decision
The system runs entirely locally: SQLite for storage, FAISS for vector
search (in-process), local LLM/VLM inference via Ollama-compatible
backends, and no cloud infrastructure, Kubernetes, microservices, Redis, or
Kafka. Complexity is added only when a concrete requirement demonstrates
it's needed.

## Consequences
- Fast iteration: no deployment pipeline, network latency, or
  infrastructure-as-code to maintain while the research questions are
  still being worked out.
- Evaluation and ablation runs are fully reproducible on a single machine.
- Revisit this decision only if a specific, demonstrated requirement
  emerges (e.g. multi-user deployment) — not preemptively.
