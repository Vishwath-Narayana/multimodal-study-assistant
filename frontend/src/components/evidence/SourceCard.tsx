import { useState } from "react";
import { ArtifactImage } from "./ArtifactImage";

function formatTimestamp(seconds: number): string {
  const mins = Math.floor(seconds / 60);
  const secs = Math.floor(seconds % 60);
  return `${mins}:${secs.toString().padStart(2, "0")}`;
}

export interface NormalizedSource {
  chunk_id: string;
  document_id: string | null;
  filename: string | null;
  page: number | null;
  section: string | null;
  chunk_type?: string | null;
  audio_start?: number | null;
  audio_end?: number | null;
  ocr_text?: string | null;
  vlm_description?: string | null;
  table_content?: string[][] | null;
  content_preview?: string | null;
  valid?: boolean;
  status?: string;
  rank?: number;
}

const MODALITY_LABEL: Record<string, string> = {
  image: "Image",
  diagram: "Diagram",
  table: "Table",
  equation: "Equation",
  transcript: "Audio transcript",
  text: "Text",
};

export function SourceCard({ source, index }: { source: NormalizedSource; index: number }) {
  const [expanded, setExpanded] = useState(false);
  const modality = source.chunk_type ?? "text";
  const hasExpandable =
    modality === "image" ||
    modality === "diagram" ||
    modality === "table" ||
    !!source.ocr_text ||
    !!source.vlm_description ||
    !!source.content_preview;

  const locationParts: string[] = [];
  if (source.page != null) locationParts.push(`Page ${source.page}`);
  if (source.section) locationParts.push(`Section: ${source.section}`);
  if (source.audio_start != null && source.audio_end != null) {
    locationParts.push(`${formatTimestamp(source.audio_start)}–${formatTimestamp(source.audio_end)}`);
  }

  return (
    <li className="rounded-lg border border-border bg-bg px-4 py-3 text-sm">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div className="flex min-w-0 flex-col gap-0.5">
          <p className="font-medium text-text">
            [{index}] {source.filename ?? "Unknown document"}
          </p>
          {locationParts.length > 0 && (
            <p className="text-xs text-text-muted">{locationParts.join(" · ")}</p>
          )}
          <div className="mt-1 flex flex-wrap items-center gap-1.5">
            <span className="rounded-full border border-border px-2 py-0.5 text-[11px] text-text-muted">
              {MODALITY_LABEL[modality] ?? modality}
            </span>
            {source.status && (
              <span
                className={`rounded-full border px-2 py-0.5 text-[11px] ${
                  source.valid
                    ? "border-emerald-900/50 text-emerald-300"
                    : "border-amber-900/50 text-amber-300"
                }`}
              >
                {source.status}
              </span>
            )}
          </div>
        </div>
        {hasExpandable && (
          <button
            type="button"
            onClick={() => setExpanded((v) => !v)}
            aria-expanded={expanded}
            className="shrink-0 rounded-lg border border-border px-2 py-1 text-xs text-text-muted hover:text-text focus-visible:outline focus-visible:outline-2 focus-visible:outline-accent"
          >
            {expanded ? "Hide" : "Show"}
          </button>
        )}
      </div>

      {expanded && (
        <div className="mt-3 flex flex-col gap-2 border-t border-border pt-3">
          {(modality === "image" || modality === "diagram") && (
            <ArtifactImage chunkId={source.chunk_id} alt={source.vlm_description ?? "Source image"} />
          )}
          {source.vlm_description && (
            <p className="text-xs text-text-muted">
              <span className="font-medium text-text">Description: </span>
              {source.vlm_description}
            </p>
          )}
          {source.ocr_text && (
            <p className="text-xs text-text-muted">
              <span className="font-medium text-text">OCR text: </span>
              {source.ocr_text}
            </p>
          )}
          {modality === "table" && source.table_content && source.table_content.length > 0 && (
            <div className="overflow-x-auto">
              <table className="min-w-full border-collapse text-xs">
                <tbody>
                  {source.table_content.map((row, rowIdx) => (
                    <tr key={rowIdx}>
                      {row.map((cell, cellIdx) => (
                        <td
                          key={cellIdx}
                          className="border border-border px-2 py-1 text-text-muted"
                        >
                          {cell}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          {source.content_preview && (
            <p className="text-xs text-text-muted">{source.content_preview}</p>
          )}
        </div>
      )}
    </li>
  );
}
