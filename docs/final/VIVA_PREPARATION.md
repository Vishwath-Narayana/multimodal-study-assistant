# Viva Preparation

Likely questions with concise, technically correct answers, grounded in
what this project actually implements and measures.

## Core RAG Concepts

**What is RAG?**
Retrieval-Augmented Generation: instead of an LLM answering purely from
its trained-in knowledge, relevant text is first retrieved from an
external corpus and given to the model as context, so answers can be
grounded in and traceable to real source documents.

**Why RAG instead of a pure LLM?**
A pure LLM can only answer from what it memorized during training — it
has no access to a specific student's documents, can't cite a verifiable
source, and can confidently hallucinate. RAG grounds answers in retrieved
evidence and lets the system say "I don't have enough evidence" instead
of guessing.

**What is BM25?**
A lexical (keyword-based) ranking function estimating relevance from term
frequency and inverse document frequency, with length normalization. It's
fast, has no training/embedding cost, and is strong on exact
terminology/keyword matches — but weak on paraphrase or semantic
similarity.

**What is dense retrieval?**
Retrieval using vector embeddings: both the query and each chunk are
embedded into the same vector space, and the closest chunks by similarity
(cosine/inner-product) are retrieved. Captures semantic similarity even
without exact keyword overlap.

**Why BGE-small (`BAAI/bge-small-en-v1.5`)?**
A small, CPU-friendly, strong-for-its-size open embedding model —
appropriate for a local-first system with no GPU dependency requirement,
matching the project's local-first constraint (ADR-002).

**What is FAISS?**
Facebook AI Similarity Search — a library for efficient nearest-neighbor
search over dense vectors. This project uses `IndexFlatIP` (exact inner-
product search), appropriate at the corpus sizes this local-first system
targets; it does not need FAISS's approximate-search indexes at this
scale.

**Why hybrid retrieval (BM25 + dense)?**
Lexical and dense retrieval fail on different classes of query — BM25
misses paraphrases, dense retrieval can miss exact rare terms/codes/
numbers. Combining both covers more of the query space than either alone.

**What is RRF (Reciprocal Rank Fusion)?**
A rank-based (not score-based) fusion method: each document's fused score
is `Σ 1/(k + rank_i)` summed across each retriever's ranked list (k=60 in
this project). It avoids the score-scale-normalization problem of
combining BM25 scores (unbounded) with cosine/dot-product scores
(bounded), because it only uses rank position.

**Why RRF specifically (over simple score fusion)?**
Measured on the pilot corpus, hybrid RRF (MRR 0.854) outperformed naive
score-averaging fusion (MRR 0.722) — rank-based fusion is more robust to
scale mismatch between BM25 and dense scores than naive averaging.

**What is HyDE?**
Hypothetical Document Embeddings: instead of embedding the raw query, a
small LLM first generates a hypothetical answer passage, and that
passage is embedded for dense retrieval — the idea being a hypothetical
answer is closer in embedding space to real answer passages than a short
question is. **Not measured with a real model in this project** — Ollama
was unavailable in the evaluation/development environment; only the
pipeline plumbing was validated with a mocked HyDE call.

**Why rerank?**
The fused candidate list is efficient to produce but coarse; a
cross-encoder reranker jointly encodes (query, candidate) pairs — more
expensive per pair but more accurate — to reorder just the top candidates.

**What is a cross-encoder (vs. a bi-encoder)?**
A bi-encoder (used for BM25/dense retrieval here) embeds query and
document independently, enabling fast large-scale search. A cross-encoder
(`cross-encoder/ms-marco-MiniLM-L-6-v2` here) encodes the query and
document *together* in one forward pass, capturing richer interaction —
more accurate but too slow to run over an entire corpus, so it's used
only to rerank a small top-k candidate set.

**What is grounding?**
Tying a generated answer's claims back to the specific retrieved evidence
that supports them — via citations (chunk-level) and token grounding
(token/claim-level match between answer text and evidence text).

**What is hallucination?**
An LLM generating a plausible-sounding but unsupported or false claim.
This project mitigates it structurally — not by prompting alone — through
mandatory evidence-sufficiency checking (no evidence → no generation
call), citation validation (only real, current-request chunk ids are
accepted), and token grounding (flagging ungrounded claims).

**What is citation validity?**
Whether a citation attached to an answer actually refers to a chunk that
was part of *this request's* retrieved evidence. `DeterministicCitation
Validator` checks this server-side and rejects fabricated, stale
(prior-request), or cross-request citation ids — verified with 8
dedicated attack tests.

**What is token grounding?**
Matching each token/claim in the generated answer back to the retrieved
evidence text (exact / word-stem / substring match), producing a
`grounding_ratio` — a measure of how much of the answer is textually
traceable to evidence, as opposed to a single opaque "confidence" number.

**What is evidence sufficiency?**
A pre-generation check (`HeuristicSufficiencyChecker`, based on chunk
count and score thresholds) that decides whether retrieved evidence is
adequate to answer at all. If not, generation is skipped entirely.

**Why abstain instead of always answering?**
Because answering confidently without adequate evidence is exactly the
hallucination failure mode this project is designed to avoid. Abstention
is a first-class, tested behavior, not an afterthought — and because it
happens *before* any LLM call, an abstention response cannot itself
contain a hallucinated claim.

## Multimodal

**How does multimodal processing work?**
Docling extracts images/tables/text during parsing. Each extracted image
is independently OCR'd and described by a vision-language model (when
configured); the OCR text, VLM description, and surrounding section text
are merged into one searchable text representation per chunk, while the
original image bytes are always separately preserved (`artifacts` table)
— so the searchable text is a *supplement*, never a lossy replacement.

**How are tables handled?**
Docling extracts table structure; table chunks retain their structured
content field (`table_content`) alongside the flattened searchable text,
so a table citation can show its full structured content, not just a
caption.

**How are diagrams/images handled?**
Same pipeline as photos — Docling's `PICTURE` label doesn't distinguish a
diagram from a photo, so both are `BlockType.IMAGE`. This is a documented
parser limitation, not a missing project feature.

**How are transcripts handled?**
Audio is transcribed via Whisper (faster-whisper) into timestamp-aware
transcript chunks (`audio_start`/`audio_end` in seconds), so a citation
into an audio source can point to the exact time range, not just "this
audio file."

## Model / Infrastructure Choices

**Why DeepSeek-R1 (or whichever current LLM)?**
`LLM_MODEL` is configured (not hardcoded) — the default in
`.env.example` is `deepseek-r1:8b` via Ollama, chosen as a capable local
model runnable without a cloud API key, consistent with the local-first
design goal. The generation interface (`Generator`/`OllamaGenerator`) is
provider-agnostic and swappable — confirm the actual configured value
against `backend/.env` or `.env.example` before answering, don't assume.

**Why local-first?**
Student documents may be sensitive (coursework, personal notes); a
local-first design avoids sending that content to a third-party cloud
API by default, and avoids a hosting/cost dependency for a bounded,
single-user academic project. See `docs/decisions/ADR-002-local-first.md`.

**Why SQLite (not PostgreSQL)?**
The project is explicitly single-user/local-first — SQLite requires no
separate server process, has zero operational overhead for this scale,
and is sufficient for the document/chunk/artifact/study-item volumes a
single student would generate. PostgreSQL's concurrency/multi-tenant
features aren't needed at this scope.

## Evaluation

**What are the evaluation metrics?**
MRR, Recall@k, Precision@k, Hit Rate@k, nDCG@k — standard information-
retrieval metrics, implemented in `app.benchmarking.metrics_ext` on top
of the existing (unmodified) `app.retrieval.evaluation.metrics`.

**What is MRR?**
Mean Reciprocal Rank: the average, across queries, of `1/rank` of the
first relevant result. Rewards relevant results appearing early.

**What is Recall@5?**
The fraction of all relevant (gold) chunks for a query that appear
anywhere in the top-5 retrieved results.

**Why did reranking reduce MRR but improve Recall@5?**
Reranking reorders the fused candidate list using a more accurate
pairwise model, which can surface *more* relevant chunks somewhere within
the top-5 (raising recall/precision) while occasionally not placing the
single most relevant chunk at rank 1 as consistently as RRF's fusion did
on this specific corpus (lowering MRR). It's a genuine precision/recall-
vs-top-rank trade-off — observed directly in the pilot results, not a
bug, and neither difference is statistically significant at n=12.

**What did the chunking experiment show?**
A ~2.19× token-inflation ratio between real BGE subword tokenization and
a whitespace-token approximation, but no pilot chunk actually exceeded
the 512-token chunking threshold under either method — so switching to
token-aware chunking produced no measurable retrieval difference on this
corpus, and the simpler whitespace approximation was kept. A valid
negative result, reported rather than hidden.

**What are the limitations?**
See `docs/final/FINAL_PROJECT_REPORT_CONTENT.md` §"Limitations" — small
pilot corpus, no statistical significance, no live generation/HyDE/VLM/
OCR benchmark, no direct visual embedding retrieval, single-user/no-auth
scope, prompt injection not eliminable.

## Security

**What security threats exist in a RAG system?**
Malicious uploads (crafted files exploiting a parser), path traversal via
filenames, prompt injection (direct, via the user's query, or indirect,
via retrieved document content), document poisoning (false-but-
well-formed content), citation/provenance forgery, resource exhaustion
(oversized documents/queries), unsafe error exposure (leaking internal
detail), and — more generally — any web-API attack class (malformed
input, injection into logs, etc.).

**What is indirect prompt injection?**
An attack where malicious instructions are embedded inside *retrieved
document content* (not the user's own query), attempting to hijack the
LLM's behavior when that content is placed into the prompt as "evidence."

**How did you mitigate it?**
Structurally, not just by prompting: evidence is framed as clearly
labeled, separated data in the prompt (never merged with instructions);
a literal-marker-neutralization step
(`app.generation.prompt_security.neutralize_prompt_markers`) breaks any
attempt to forge a section-boundary marker (e.g. `=== STUDENT QUESTION
===`) inside chunk content before it enters the prompt; and a log-only
heuristic scanner (`app.generation.injection_detection`) flags
injection-shaped evidence for visibility without blocking legitimate
academic content. **None of this guarantees a live LLM can never be
influenced by adversarial context text** — stated explicitly as a
residual risk, not claimed as solved.

**What is document poisoning?**
Uploading factually false but well-formed content designed to make the
system state it as fact. This project does not attempt to detect
false-but-well-formed content (that's a factual-accuracy problem, not a
security-boundary one); the mitigation is provenance integrity — a
poisoned answer is still correctly and verifiably traced to its exact
source chunk, so a reader can check and reject it, rather than it being
presented as verified fact from nowhere.

**What is future work?**
See `docs/final/FINAL_PROJECT_REPORT_CONTENT.md` §"Future Work" — full
benchmark once local models are available, direct visual embedding
retrieval, authentication/multi-tenancy if scope changes, statistically
powered evaluation, live adversarial-model injection testing.

---

## Architecture Explanation Scripts

### 30-second version

"A student's question goes through hybrid retrieval — BM25 keyword search
and dense embedding search combined with Reciprocal Rank Fusion — then a
cross-encoder reranks the top results. If there isn't enough good
evidence, the system abstains. Otherwise a local LLM generates an answer
grounded in that evidence, and every citation and claim is checked
against the actual retrieved chunks before the answer is returned."

### 60–90 second version

"When a student asks a question, the query is run through two retrievers
in parallel: BM25 for exact keyword/lexical matching, and dense retrieval
— embedding the query with BGE-small and searching a FAISS index — for
semantic similarity. Their two ranked lists are combined with Reciprocal
Rank Fusion, which merges them by rank position rather than raw score, so
BM25's and the embedding model's very different score scales don't need
manual normalization. The fused top candidates then go through a
cross-encoder reranker, which jointly encodes the query and each
candidate for a more accurate — if more expensive — relevance judgment,
producing the final top-k evidence set. Before generating anything, an
evidence-sufficiency check decides whether that evidence is actually
adequate; if not, the system returns an explicit abstention with no model
call at all. If it is sufficient, a local LLM generates an answer using
that evidence as strictly-labeled context data, never as instructions.
The generated answer's citations are then validated server-side against
the real evidence set for this exact request — a fabricated or stale
citation is rejected — and each claim is checked for token-level
grounding against the evidence text. The same pipeline, unmodified,
backs six study-generation modes: summaries, explanations, comparisons,
quizzes, MCQs, and flashcards."

### 2-minute detailed version

Use the 60–90s version above, then add: "Beyond the core pipeline, the
system extends to multimodal content — Docling parses PDFs/DOCX/PPTX/
HTML and extracts images and tables during ingestion; each image is
independently OCR'd and described by a vision-language model, merged
into the same kind of searchable chunk text as regular paragraphs, while
the original image bytes are always preserved separately and never
replaced by that description. Audio is transcribed via Whisper into
timestamp-aware chunks, so an audio citation can point to an exact time
range in the source recording. On the security side, the whole pipeline
was hardened in a dedicated phase against RAG-specific threats: uploads
are validated by actual file content, not just extension; retrieved
evidence text is structurally prevented from forging prompt-section
markers; citations are validated against real, current-request evidence
server-side, not trusted from model output; and resource ceilings bound
document size, chunk count, and query length. All of this is deliberately
scoped to a local-first, single-user deployment — there's no
authentication or multi-tenant isolation, by design, and that's stated
explicitly rather than glossed over. On the evaluation side, the
retrieval pipeline was measured — not estimated — on a small pilot
corpus: hybrid RRF gives the best top-rank accuracy, reranking gives the
best recall, and I can show exactly why, and exactly how small and
non-significant those pilot numbers are, rather than overclaiming them."

## Project Differentiation

**"How is your project different from a normal chatbot?"**

1. **Student-owned data**: it only answers from documents the student
   actually uploaded, not from general training knowledge.
2. **Retrieval grounding**: every answer is backed by hybrid BM25+dense
   retrieval over that student's own corpus, not free generation.
3. **Citations**: every claim carries a citation that is validated
   server-side against real retrieved evidence — not a decorative,
   model-generated reference that could be fabricated.
4. **Multimodal evidence**: images, diagrams, tables, and audio
   transcripts are first-class retrievable, citable evidence — not
   ignored or reduced to lossy captions.
5. **Abstention**: when evidence is insufficient, the system says so
   explicitly instead of generating a plausible-sounding guess — checked
   *before* any model call.
6. **Explainability**: token-level grounding and contradiction detection
   give a machine-checkable signal for how well an answer is actually
   supported by evidence, beyond "the model said so."
7. **Study modes**: the same grounded, cited infrastructure powers
   structured study-content generation (quizzes, MCQs, flashcards,
   summaries, comparisons), not just open-ended chat.
8. **Security controls**: hardened against RAG-specific attacks
   (indirect prompt injection via document content, citation forgery,
   malicious uploads) with a documented, tested threat model — not an
   afterthought bolted onto a chat demo.
