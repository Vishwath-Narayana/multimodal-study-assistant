# System Architecture

Status: **design document**. Only the pieces explicitly marked "implemented"
exist in code today (Phase 0: FastAPI app skeleton + `/health`). Everything
else describes the intended architecture that will be built phase-by-phase
per [docs/roadmap.md](../roadmap.md).

## 1. High-Level Architecture

```mermaid
flowchart TD
    Student --> Frontend
    Frontend --> API[FastAPI]
    API --> QP[Query Processor]
    QP --> QI[Query Intent / Rewrite]
    QI --> BM25[BM25 - Original Query]
    QI --> FAISS[FAISS - HyDE Query]
    BM25 --> RRF[Reciprocal Rank Fusion]
    FAISS --> RRF
    RRF --> RR[Cross-Encoder Reranker]
    RR --> ES[Evidence Selection]
    ES --> SUFF{Evidence Sufficiency}
    SUFF -->|insufficient| ABSTAIN[Abstain]
    SUFF -->|sufficient| LLM[Grounded Generation]
    LLM --> CV[Citation Validation]
    CV --> TG[Token Grounding]
    TG --> CC[Contradiction Check]
    CC --> FINAL[Final Answer]
```

Evidence sufficiency, abstention, and contradiction checking are **proposed
extensions** (see README §7), not part of the reproduced EduRAG baseline —
they are included in this diagram because they sit in the request path once
built, but the baseline pipeline (README §6) stops at reranking → generation
→ explainability.

## 2. Ingestion Pipeline

Status: **implemented for Phase 1** through structure-aware chunking and
SQLite persistence — see [docs/architecture/ingestion.md](ingestion.md)
for the actual pipeline, canonical model, and documented limitations.
Embedding and FAISS indexing (below) are **implemented for Phase 2** — see
[docs/architecture/retrieval.md](retrieval.md); perceptual-hash image
dedup and VLM/OCR description remain Phase 5.

```mermaid
flowchart LR
    Upload --> Validate[Validate + SHA-256 hash]
    Validate --> Parse[Docling parsing]
    Parse --> Extract[Text / tables / images / equations]
    Extract --> Chunk[Structure-aware chunking, ~512 tokens]
    Chunk --> Store[(SQLite: documents, chunks)]
    Store -.Phase 5.-> Dedup[Perceptual-hash dedup for images]
    Store -.Phase 5.-> Visual[VLM description + OCR]
    Store -.Phase 2.-> Embed[Embed chunks - bge-small-en-v1.5]
    Embed -.Phase 2.-> Index[(FAISS index)]
```

Each chunk retains provenance: source document, page/section, chunk type
(heading/paragraph/list/table/image/equation/code/caption), and — for
image chunks — the extracted image path (where Docling provides the
bytes; see ingestion.md for the HTML exception). OCR text and VLM
descriptions are Phase 5 additions, not yet implemented.

## 3. Retrieval Pipeline

Status: **implemented for Phase 2** — see
[docs/architecture/retrieval.md](retrieval.md) for the full design
(domain model, BM25/dense/hybrid/RRF/HyDE/reranking architecture, index
lifecycle, retrieval modes, trace/observability, error behavior, and the
explicit EduRAG-baseline-vs-implementation-choice list). Query intent
classification/rewrite (beyond HyDE) is not part of Phase 2 — the diagram
below is the Phase 2 `full_baseline` mode; `dense`/`hybrid_rrf`/etc. are
separately selectable subsets of this same pipeline, not implemented as
new diagrams here.

```mermaid
flowchart TD
    Query --> Orig[Original Query]
    Query --> HyDE[HyDE-generated hypothetical passage]
    Orig --> BM25
    HyDE --> FAISS
    BM25 --> RRF[RRF, k=60 baseline]
    FAISS --> RRF
    RRF --> Rerank[Cross-Encoder Reranker]
    Rerank --> TopK[Top-K Evidence]
```

## 4. Generation Pipeline

```mermaid
flowchart LR
    TopK[Top-K Evidence] --> Prompt[Prompt Construction]
    Prompt --> LLM[Local LLM via Ollama]
    LLM --> Answer[Draft Answer]
```

Prompt construction treats retrieved chunk text strictly as **data**, never
as instructions — see [docs/research/security.md](../research/security.md).

## 5. Explainability Pipeline

```mermaid
flowchart LR
    Answer[Draft Answer] --> Attr[Chunk Attribution]
    Attr --> CiteVal[Citation Validation]
    CiteVal --> Ground[Token Grounding<br/>exact / stem / substring match]
    Ground --> Penalty[Unsupported Token Penalty]
    Penalty --> Final[Final Answer + Citations + Scores]
```

## 6. Study Engine

```mermaid
flowchart LR
    Evidence[Selected Evidence] --> Gen[Study-Item Generator]
    Gen --> Summary[Summary]
    Gen --> Quiz[Quiz]
    Gen --> MCQ[MCQ]
    Gen --> Flash[Flashcards]
    Gen --> Compare[Comparison]
```

Every generated study item stores its `source_chunk_ids` so it remains
traceable back to evidence (see [docs/architecture/database.md](database.md)).

## 7. Evaluation Architecture

```mermaid
flowchart LR
    Config[Experiment Config] --> Run[Pipeline Run]
    Run --> Metrics[Retrieval / Generation / Trust Metrics]
    Metrics --> Report[evaluation/experiments/*]
```

See [docs/research/evaluation-plan.md](../research/evaluation-plan.md) and
[docs/research/ablation-plan.md](../research/ablation-plan.md) for the
metrics and ablation matrix. Experiment configs and results are never
fabricated — reports only exist once a run has actually happened.
