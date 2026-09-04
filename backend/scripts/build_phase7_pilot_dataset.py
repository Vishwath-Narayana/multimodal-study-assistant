"""Builds the Phase 7 pilot benchmark dataset (`evaluation/datasets/pilot_v1.json`).

Mirrors `build_eval_dataset.py`'s discipline: chunk ids referenced by
questions are derived by actually running Phase 1 ingestion against the
real fixture files in `backend/tests/fixtures/`, never hand-typed. Query
text, category, and relevance judgments are curated by hand below, then
validated (schema + "does this chunk id actually exist") before being
written out.

Corpus limitation (documented, not hidden): the only real document content
available in this environment is the single-topic (cell biology) Phase 1
fixture set, parsed from three source formats (html/docx/pptx). This is a
genuine pilot, deliberately small — see docs/evaluation/DATASET.md for why
categories like contradictory-source, ambiguous-query, equation, and
real (non-mocked) image/transcript content are not populated here rather
than fabricated.

Run from `backend/`: `uv run python scripts/build_phase7_pilot_dataset.py`
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.benchmarking.schemas import BenchmarkDataset, BenchmarkQuestion, Modality, QuestionCategory
from app.ingestion.chunking import ChunkingConfig, chunk_document
from app.ingestion.hashing import sha256_bytes
from app.ingestion.parsers.docling_parser import DoclingParser
from app.ingestion.storage import DataPaths, FileImageStorage

FIXTURES_DIR = Path(__file__).resolve().parents[1] / "tests" / "fixtures"
FIXTURE_FILES = ["study_notes.html", "study_notes.docx", "study_notes.pptx"]
OUTPUT_PATH = Path(__file__).resolve().parents[2] / "evaluation" / "datasets" / "pilot_v1.json"


def _ingest_fixtures() -> tuple[dict[str, str], dict[str, set[str]]]:
    """Returns (filename -> document_id, document_id -> set of real chunk ids)."""
    scratch = Path("/tmp/build_phase7_pilot_dataset_scratch")
    scratch.mkdir(exist_ok=True)
    paths = DataPaths(str(scratch))
    parser = DoclingParser(image_storage=FileImageStorage(paths))
    config = ChunkingConfig(target_tokens=512, overlap_tokens=50)

    documents: dict[str, str] = {}
    chunk_ids_by_doc: dict[str, set[str]] = {}
    for filename in FIXTURE_FILES:
        data = (FIXTURES_DIR / filename).read_bytes()
        file_hash = sha256_bytes(data)
        doc = parser.parse(
            FIXTURES_DIR / filename, document_id=file_hash, filename=filename, file_hash=file_hash
        )
        chunks = chunk_document(doc.id, doc.blocks, config)
        documents[filename] = file_hash
        chunk_ids_by_doc[file_hash] = {c.id for c in chunks}
    return documents, chunk_ids_by_doc


def _cid(doc_id: str, n: int) -> str:
    return f"{doc_id}::chunk::{n:05d}"


def main() -> None:
    documents, chunk_ids_by_doc = _ingest_fixtures()
    html = documents["study_notes.html"]
    docx = documents["study_notes.docx"]
    pptx = documents["study_notes.pptx"]

    questions = [
        BenchmarkQuestion(
            question_id="p001",
            question="What does photosynthesis convert light energy into?",
            category=QuestionCategory.FACTUAL,
            modality=Modality.TEXT,
            answerable=True,
            source_documents=[html, docx],
            gold_chunk_ids=[_cid(html, 3), _cid(docx, 3)],
            gold_answer="Chemical energy stored in glucose.",
            acceptable_answers=["chemical energy", "chemical energy stored in glucose"],
        ),
        BenchmarkQuestion(
            question_id="p002",
            question="What is cellular respiration?",
            category=QuestionCategory.DEFINITION,
            modality=Modality.TEXT,
            answerable=True,
            source_documents=[html, docx, pptx],
            gold_chunk_ids=[_cid(html, 6), _cid(docx, 6), _cid(pptx, 3)],
            gold_answer=(
                "The process that releases energy stored in glucose through glycolysis, "
                "the citric acid cycle, and oxidative phosphorylation."
            ),
            acceptable_answers=["releases energy stored in glucose"],
        ),
        BenchmarkQuestion(
            question_id="p003",
            question="Which organelle is responsible for ATP production?",
            category=QuestionCategory.TABLE,
            modality=Modality.TABLE,
            answerable=True,
            source_documents=[html, docx, pptx],
            gold_chunk_ids=[_cid(html, 4), _cid(docx, 4), _cid(pptx, 5)],
            gold_answer="Mitochondria.",
            acceptable_answers=["mitochondria", "the mitochondria"],
        ),
        BenchmarkQuestion(
            question_id="p004",
            question="According to the table, what is the chloroplast responsible for?",
            category=QuestionCategory.TABLE,
            modality=Modality.TABLE,
            answerable=True,
            source_documents=[html, docx, pptx],
            gold_chunk_ids=[_cid(html, 4), _cid(docx, 4), _cid(pptx, 5)],
            gold_answer="Photosynthesis.",
            acceptable_answers=["photosynthesis"],
        ),
        BenchmarkQuestion(
            question_id="p005",
            question="What is covered in Section 1.2, Cellular Respiration?",
            category=QuestionCategory.FACTUAL,
            modality=Modality.TEXT,
            answerable=True,
            source_documents=[html, pptx],
            gold_chunk_ids=[_cid(html, 6), _cid(pptx, 3)],
            gold_answer="Cellular respiration releasing energy via glycolysis, the citric acid cycle, and oxidative phosphorylation.",
            acceptable_answers=["glycolysis"],
        ),
        BenchmarkQuestion(
            question_id="p006",
            question="What is photosynthesis?",
            category=QuestionCategory.CROSS_DOCUMENT,
            modality=Modality.TEXT,
            answerable=True,
            source_documents=[html, docx, pptx],
            gold_chunk_ids=[_cid(html, 3), _cid(docx, 3), _cid(pptx, 1)],
            gold_answer="The conversion of light energy into chemical energy stored in glucose, occurring in chloroplasts.",
            acceptable_answers=["converts light energy into chemical energy"],
            note="Same underlying content appears in three document formats (html/docx/pptx); tests cross-document retrieval consistency, not three independent sources.",
        ),
        BenchmarkQuestion(
            question_id="p007",
            question="What is the powerhouse of the cell?",
            category=QuestionCategory.FACTUAL,
            modality=Modality.TABLE,
            answerable=True,
            source_documents=[html, docx],
            gold_chunk_ids=[_cid(html, 4), _cid(docx, 4)],
            gold_answer="The mitochondria.",
            acceptable_answers=["mitochondria"],
            note="Common-knowledge phrasing not used verbatim in the source text; tests whether retrieval bridges the lexical gap to the organelle/function table.",
        ),
        BenchmarkQuestion(
            question_id="p008",
            question="Name both organelles discussed in the notes and what each one does.",
            category=QuestionCategory.MULTI_HOP,
            modality=Modality.TEXT,
            answerable=True,
            source_documents=[html, docx],
            gold_chunk_ids=[_cid(html, 3), _cid(html, 4), _cid(docx, 3), _cid(docx, 4)],
            gold_answer="Chloroplasts carry out photosynthesis; mitochondria produce ATP.",
            acceptable_answers=["chloroplast", "mitochondria"],
            note="Requires combining the organelle/function table with the photosynthesis paragraph; a single-chunk retrieval that only returns one of the two is a partial (not full) hit.",
        ),
        BenchmarkQuestion(
            question_id="p009",
            question="How does photosynthesis differ from cellular respiration in terms of energy flow?",
            category=QuestionCategory.COMPARISON,
            modality=Modality.TEXT,
            answerable=True,
            source_documents=[html, docx, pptx],
            gold_chunk_ids=[
                _cid(html, 3),
                _cid(html, 6),
                _cid(docx, 3),
                _cid(docx, 6),
                _cid(pptx, 1),
                _cid(pptx, 3),
            ],
            gold_answer=(
                "Photosynthesis converts light energy into stored chemical energy (glucose); "
                "cellular respiration releases that stored energy from glucose."
            ),
            acceptable_answers=["photosynthesis stores", "respiration releases"],
        ),
        BenchmarkQuestion(
            question_id="p010",
            question="Explain the light-dependent reactions of photosynthesis.",
            category=QuestionCategory.EXPLANATION,
            modality=Modality.TEXT,
            answerable=True,
            source_documents=[html, docx, pptx],
            gold_chunk_ids=[_cid(html, 3), _cid(docx, 3), _cid(pptx, 1)],
            gold_answer="Light absorption by chlorophyll, an electron transport chain, then ATP and NADPH synthesis.",
            acceptable_answers=["light absorption", "electron transport chain", "ATP and NADPH"],
        ),
        BenchmarkQuestion(
            question_id="p011",
            question="What does the plant cell diagram show?",
            category=QuestionCategory.IMAGE,
            modality=Modality.IMAGE,
            answerable=True,
            source_documents=[html, docx],
            gold_chunk_ids=[_cid(html, 7), _cid(html, 8), _cid(docx, 8)],
            gold_answer=None,
            acceptable_answers=[],
            note=(
                "No VLM is available in this environment (see docs/evaluation/reference_paper.md "
                "and Phase 4 known limitations), so this question is retrieval-only: it checks "
                "whether the image/caption chunk is retrieved, not whether a generated description "
                "is correct. gold_answer is intentionally left unset rather than fabricated."
            ),
        ),
        BenchmarkQuestion(
            question_id="p012",
            question="What does the notes set say about glycolysis, the citric acid cycle, and oxidative phosphorylation?",
            category=QuestionCategory.EXPLANATION,
            modality=Modality.TEXT,
            answerable=True,
            source_documents=[html, docx, pptx],
            gold_chunk_ids=[_cid(html, 6), _cid(docx, 6), _cid(pptx, 3)],
            gold_answer="They are the three stages through which cellular respiration releases energy stored in glucose.",
            acceptable_answers=["glycolysis", "citric acid cycle", "oxidative phosphorylation"],
        ),
        BenchmarkQuestion(
            question_id="p013",
            question="What is the measured rate of nitrogen fixation described in these notes?",
            category=QuestionCategory.UNANSWERABLE,
            modality=Modality.TEXT,
            answerable=False,
            source_documents=[html, docx, pptx],
            gold_chunk_ids=[],
            note="Nitrogen fixation is not covered anywhere in the pilot corpus (photosynthesis/cellular respiration only); tests abstention rather than hallucination.",
        ),
        BenchmarkQuestion(
            question_id="p014",
            question="What safety precautions does the document describe for extracting mitochondrial DNA?",
            category=QuestionCategory.UNANSWERABLE,
            modality=Modality.TEXT,
            answerable=False,
            source_documents=[html, docx, pptx],
            gold_chunk_ids=[],
            note="No extraction-protocol or safety content exists in the pilot corpus; tests abstention.",
        ),
    ]

    dataset = BenchmarkDataset(
        dataset_id="pilot_v1",
        description=(
            "Phase 7 pilot benchmark (7B-1). Built directly against the real Phase 1 fixtures "
            "in backend/tests/fixtures/ (study_notes.html/.docx/.pptx) — a single cell-biology "
            "topic parsed from three source formats, real BM25/BGE/FAISS ingestion, no VLM/OCR/"
            "Whisper content (none available in this environment; see docs/evaluation/DATASET.md). "
            "Deliberately small: no other real academic corpus was available when this pilot was "
            "built (see docs/evaluation/DATASET.md 'Limitations'). Regenerate with "
            "backend/scripts/build_phase7_pilot_dataset.py if a fixture file's content changes."
        ),
        documents=documents,
        questions=questions,
        limitations=[
            "Single subject area (cell biology) — target of 5-10 subject areas not met; no other real academic material was available (see stop-condition discussion in the Phase 7 session log).",
            "contradictory-source and ambiguous-query categories are not populated: the pilot corpus contains no genuinely conflicting statements, and a fabricated contradiction would violate the no-fabrication rule.",
            "equation category is not populated: Docling formula enrichment is disabled (Phase 1 decision), so no fixture produces a real EQUATION chunk.",
            "transcript category is not populated with real audio content: no real Whisper transcription is available in this environment (Phase 4's mocked-transcript fixture exists only for pipeline wiring, not as benchmark ground truth).",
            "image question (p011) is retrieval-only: no VLM is available, so image/caption *content* quality is not evaluated, only whether the correct chunk is retrieved.",
        ],
    )

    problems = dataset.validate()
    if problems:
        raise SystemExit(f"Dataset failed validation: {json.dumps(problems, indent=2)}")

    for q in dataset.questions:
        for cid in q.gold_chunk_ids:
            doc_id = cid.split("::chunk::")[0]
            if cid not in chunk_ids_by_doc.get(doc_id, set()):
                raise SystemExit(
                    f"{q.question_id}: gold chunk id {cid!r} does not exist in real ingestion output"
                )

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "dataset_id": dataset.dataset_id,
        "description": dataset.description,
        "documents": dataset.documents,
        "limitations": dataset.limitations,
        "questions": [q.to_dict() for q in dataset.questions],
    }
    OUTPUT_PATH.write_text(json.dumps(payload, indent=2, sort_keys=False) + "\n")
    print(f"Wrote {len(dataset.questions)} questions to {OUTPUT_PATH}")
    print(json.dumps(dataset.stats(), indent=2))


if __name__ == "__main__":
    main()
