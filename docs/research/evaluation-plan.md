# Evaluation Plan

Status: **plan only**. No evaluation harness or datasets exist yet
(Phase 0). This defines what will be measured once retrieval and generation
are implemented (Phase 2+), so evaluation is designed alongside the system
rather than bolted on afterward.

## Retrieval Metrics

- MRR (Mean Reciprocal Rank)
- Recall@1
- Recall@5
- Precision@K

## Generation Metrics

- BERTScore F1
- ROUGE-L
- Token F1

## Trust / Grounding Metrics

- Faithfulness
- Citation validity
- Token grounding ratio
- Unsupported claim rate

## Multimodal Metrics

- Visual retrieval accuracy
- Table retrieval accuracy
- Diagram retrieval accuracy
- Transcript retrieval accuracy
- Timestamp citation accuracy

## Proposed Research Metrics (for our extensions)

- Contradiction detection precision / recall / F1
- Correct abstention rate
- False-answer rate
- Evidence sufficiency accuracy

## Process

1. Every run uses an explicit configuration (see
   [docs/research/reproducibility.md](reproducibility.md)).
2. Results are written under `evaluation/experiments/<run-id>/` alongside
   the configuration that produced them.
3. No metric value is written into any document (README, ADRs, papers)
   until the run that produced it exists in `evaluation/experiments/`.
4. Baseline (reproduced EduRAG) results are recorded separately from
   results including our extensions, so improvements can be attributed
   correctly — see [docs/research/ablation-plan.md](ablation-plan.md).
