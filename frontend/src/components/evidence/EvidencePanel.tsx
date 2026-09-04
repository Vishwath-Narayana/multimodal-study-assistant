import type { Citation, EvidenceItem } from "../../lib/api";
import { SourceCard, type NormalizedSource } from "./SourceCard";

function fromEvidence(item: EvidenceItem): NormalizedSource {
  return {
    chunk_id: item.chunk_id,
    document_id: item.document_id,
    filename: item.filename,
    page: item.page,
    section: item.section,
    chunk_type: item.chunk_type,
    audio_start: item.audio_start,
    audio_end: item.audio_end,
    ocr_text: item.ocr_text,
    vlm_description: item.vlm_description,
    table_content: item.table_content,
    content_preview: item.content_preview,
    rank: item.rank,
  };
}

function fromCitation(citation: Citation): NormalizedSource {
  return {
    chunk_id: citation.chunk_id,
    document_id: citation.document_id,
    filename: citation.filename,
    page: citation.page,
    section: citation.section,
    chunk_type: citation.chunk_type,
    audio_start: citation.audio_start,
    audio_end: citation.audio_end,
    valid: citation.valid,
    status: citation.status,
  };
}

/** "Sources" panel for an answer's validated citations — the primary
 * evidence/citation UI (spec section 8/9): every answer with evidence
 * shows exactly what grounded it, including multimodal fields. */
export function CitationPanel({ citations }: { citations: Citation[] }) {
  if (citations.length === 0) return null;
  return (
    <div className="flex flex-col gap-2">
      <p className="text-xs font-medium uppercase tracking-wide text-text-muted">Sources</p>
      <ul className="flex flex-col gap-2">
        {citations.map((citation, idx) => (
          <SourceCard key={`${citation.chunk_id}-${idx}`} source={fromCitation(citation)} index={idx + 1} />
        ))}
      </ul>
    </div>
  );
}

/** "Evidence considered" panel — the full retrieved context, shown
 * collapsed/secondary to the validated citations above (or as the main
 * explanation when an answer is abstained). */
export function EvidenceConsideredPanel({ evidence }: { evidence: EvidenceItem[] }) {
  if (evidence.length === 0) return null;
  return (
    <details className="rounded-xl border border-border bg-surface px-5 py-4">
      <summary className="cursor-pointer text-xs font-medium uppercase tracking-wide text-text-muted">
        Evidence considered ({evidence.length})
      </summary>
      <ul className="mt-3 flex flex-col gap-2">
        {evidence.map((item, idx) => (
          <SourceCard key={`${item.chunk_id}-${idx}`} source={fromEvidence(item)} index={idx + 1} />
        ))}
      </ul>
    </details>
  );
}
