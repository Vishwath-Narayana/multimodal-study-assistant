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

```mermaid
flowchart LR
    Upload --> Parse[Docling parsing]
    Parse --> Extract[Text / tables / images / equations]
    Extract --> Dedup[Perceptual-hash dedup for images]
    Dedup --> Visual[VLM description + OCR]
    Visual --> Chunk[Structure-aware chunking, ~512 tokens]
    Chunk --> Embed[Embed chunks - bge-small-en-v1.5]
    Embed --> Store[(SQLite metadata + FAISS index)]
```

Each chunk retains provenance: source document, page/section/slide,
chunk type (text/table/image/equation), and — for visual chunks — the
original image path alongside its OCR text and VLM description (not a
caption-only representation).

## 3. Retrieval Pipeline

```mermaid
flowchart TD
    Query --> Rewrite[Query Intent Classification / Rewrite]
    Rewrite --> Orig[Original Query]
    Rewrite --> HyDE[HyDE-generated hypothetical answer]
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
