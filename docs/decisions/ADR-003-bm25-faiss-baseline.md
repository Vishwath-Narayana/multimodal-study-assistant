# ADR-003: BM25 + FAISS for the Baseline Retrieval Stack

## Status
Accepted

## Context
The EduRAG baseline we are reproducing uses a hybrid lexical + dense
retrieval approach (BM25 + FAISS, fused with RRF, then reranked). This
choice is inherited from the research baseline we are reproducing, not
independently derived here — but it is also the right fit for a local-first
project.

## Decision
Use BM25 (lexical) and FAISS (dense, via `BAAI/bge-small-en-v1.5`
embeddings) as the two baseline retrievers, fused with Reciprocal Rank
Fusion and reranked with a cross-encoder, exactly matching the baseline
architecture in README §6, before any of our own extensions are added.

## Consequences
- Lexical retrieval (BM25) covers exact-term/keyword queries (definitions,
  names) that dense retrieval alone can under-serve; FAISS covers semantic
  similarity. Combining them is why the baseline uses both rather than one.
- FAISS runs in-process with no external vector database service —
  consistent with [ADR-002](ADR-002-local-first.md).
- Any future swap (e.g. a different embedding model or a different lexical
  index) must preserve comparability with the reproduced baseline numbers,
  which is why retrieval components are implemented behind swappable
  interfaces (see [ADR-004](ADR-004-model-agnostic-interfaces.md)).
