# Demo Script (7–10 minutes)

Assumes the presenter has both servers running locally
(`cd backend && uv run uvicorn app.main:app --reload`,
`cd frontend && pnpm dev`) and a fresh/near-empty document library.
**Ollama is not required to demo most of the system**, but generation
(`/chat/query`, all six `/study/*` modes) will correctly return a `503`
error if Ollama is not running — see the fallback for each affected step.
Check `ollama list` beforehand; if a model is available, generation steps
run live. If not, use the fallback script (which is itself an honest,
useful demo point: "the system fails safely and visibly, it never
fabricates an answer when it can't generate one").

## 1. Problem Introduction (~1 min)

**Say**: "Students collect study material across many formats — PDFs,
slides, scanned notes, recorded lectures — and generic AI chat tools
answer from general knowledge, not from that material, with no way to
verify the source. This project builds a study assistant that only
answers from documents you actually upload, cites exactly which chunk of
which document it used, and tells you honestly when it doesn't have
enough evidence instead of guessing."

## 2. Application Overview (~1 min)

**Click**: open the frontend at `http://localhost:5173`.
**Say**: walk through the visible sections — document library, chat,
study tools. **Expected screen**: dashboard/library view, empty or with a
couple of prior documents.

## 3. Upload a Document (~1 min)

**Click**: Upload button → select a small PDF or DOCX (see "Demo
Dataset" below).
**Say**: "The system validates the file (extension, size, and actual file
content — not just the extension), then parses and chunks it while
preserving structure — headings, sections, tables, images."
**Expected**: upload completes, status becomes "completed", chunk count
shown.
**Fallback**: if ingestion of a specific PDF is slow/unstable in the demo
environment (large Docling layout models can take time to load on first
use), have a DOCX or PPTX pre-staged as a faster alternative — the same
pipeline and guarantees apply to all supported formats.

## 4. Show Ingestion / Document Library (~30s)

**Click**: document library list.
**Say**: "Each document shows its chunk count and status. Deleting a
document cascades — removing it also removes every chunk, artifact, and
study item derived from it, verifiably (nothing orphaned)."

## 5. Ask a Grounded Question (~1.5 min)

**Click**: chat, type a question answerable from the uploaded document.
**Say**: "The question goes through hybrid retrieval — BM25 plus dense
embedding search, combined with Reciprocal Rank Fusion — then a
cross-encoder reranker refines the top results before generation."
**Expected (Ollama running)**: an answer with inline `[chunk:...]`
citation markers.
**Fallback (Ollama not running)**: the request returns `503 LLM provider
'ollama' ... is unreachable`. **Say**: "This is the system's real,
correct behavior when no local model is available — it fails visibly
rather than fabricating an answer. I can show the same request succeeding
against `/retrieval/search` directly, which doesn't need the LLM at all,"
then run step 5b below.

**5b (retrieval-only fallback)**: use the API docs (`/docs`) or a
pre-typed `curl` command against `POST /retrieval/search` with
`{"query": "...", "mode": "hybrid_rrf", "top_k": 5}` to show real ranked
results with per-stage BM25/dense/RRF scores, without needing generation.

## 6. Show Evidence / Citations (~1 min)

**Say**: "Every citation is validated against the actual retrieved
evidence for this exact request — a fabricated, stale, or borrowed
citation id is rejected. This isn't a UI-only badge; it's checked
server-side." Point at the evidence panel showing document/page/section
per citation.

## 7. Show Insufficient-Evidence Behavior (~1 min)

**Click**: ask a question clearly unrelated to the uploaded document
(e.g., about a topic never uploaded).
**Expected**: an explicit abstention response ("insufficient evidence"),
not a hallucinated answer, and no citations.
**Say**: "The evidence-sufficiency check runs before any model call — if
it fails, the LLM is never even invoked, so an abstention can't itself
hallucinate."

## 8. Multimodal Example, if executable (~1 min)

**If** a document with a table or image was uploaded: show a
question whose answer/citation comes from a table or image chunk, and
point out the citation's `chunk_type` (e.g. `"table"` or `"image"`) and,
for an image, that the original image is still viewable via its artifact
link — never replaced by a caption.
**Fallback (no VLM/OCR configured)**: **say**: "Vision-language
description and OCR require a local VLM and Tesseract, which aren't
installed in this environment. Tables are handled without either
dependency — I'll show that instead," and use a table-derived citation.

## 9. Show Summary (~45s)

**Click**: Study → Summary, scoped to the uploaded document.
**Expected (Ollama running)**: a grounded summary with citations.
**Fallback**: same `503` behavior as step 5 — **say**: "Same grounded
pipeline, same honest failure mode, no fabricated summary."

## 10. Show MCQ / Quiz (~45s)

**Click**: Study → Quiz or MCQ.
**Say**: "Every generated question stores which chunks it was generated
from, so a student can trace a quiz question back to the exact source
material." Same live/fallback behavior as step 9.

## 11. Show Flashcards (~30s)

**Click**: Study → Flashcards. Same live/fallback behavior as step 9.

## 12. Briefly Show Evaluation Results (~45s)

**Show**: `docs/evaluation/PHASE_7_EVALUATION_REPORT.md` or the results
table in `docs/final/FINAL_PROJECT_REPORT_CONTENT.md` §"Retrieval
Results".
**Say**: "On a small pilot benchmark, hybrid RRF gave the best top-rank
accuracy and reranking gave the best recall — a genuine trade-off, not a
clean win either way, and the differences aren't statistically
significant at this sample size. I'm not claiming this is a large-scale
result; it's a real, reproducible pilot measurement, reported honestly."

## 13. Briefly Mention Security (~30s)

**Say**: "The system was audited against RAG-specific threats — malicious
uploads, prompt injection through retrieved document content, citation
forgery — with 70 dedicated security tests, all passing. It's still a
local-first, single-user system with no authentication, which is a
documented, deliberate scope boundary, not an oversight."

## 14. Conclusion (~30s)

**Say**: "The core contribution is treating retrieval grounding,
citation validity, and abstention as first-class, testable behaviors —
not just prompt-engineering — across both chat and study-generation, for
multimodal student material, with an honest account of what's measured
and what isn't yet."

---

## Demo Dataset

Prefer a small, presenter-supplied set (not committed to this
repository, to avoid copyright/privacy issues):
- One short academic PDF (a few pages, not a full copyrighted textbook —
  lecture notes, a public-domain excerpt, or the presenter's own
  original notes).
- One short PPTX slide deck.
- One image/diagram (a simple labeled diagram, e.g. a cell diagram or a
  flowchart), ideally embedded in the PDF/PPTX rather than uploaded
  standalone.
- One document containing at least one clear table (pricing table,
  comparison table, or similar).

**Do not commit copyrighted textbooks, real students' private material,
or anything not owned/licensed by the presenter.** The repository's own
test fixtures (`backend/tests/fixtures/study_notes.pdf/.docx/.pptx`) are
safe, already-committed, synthetic placeholders and can be used directly
if no other material is prepared — they were used for Phase 9's own live
validation (see `docs/final/PHASE_9_FINAL_REPORT.md` §3).
