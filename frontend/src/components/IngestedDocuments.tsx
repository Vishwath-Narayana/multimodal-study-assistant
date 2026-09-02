import type { IngestionResult } from "../lib/api";

export function IngestedDocuments({ documents }: { documents: IngestionResult[] }) {
  if (documents.length === 0) {
    return null;
  }

  return (
    <div className="flex flex-col gap-2 rounded-xl border border-border bg-surface px-6 py-4">
      <p className="text-sm font-medium text-text">Uploaded documents</p>
      <ul className="flex flex-col gap-2">
        {documents.map((doc) => (
          <li
            key={doc.document_id}
            className="flex items-center justify-between rounded-lg border border-border bg-bg px-4 py-2 text-sm"
          >
            <span className="text-text">{doc.filename}</span>
            <span className="text-text-muted">
              {doc.duplicate ? "already ingested" : doc.status}
              {doc.status === "completed" && !doc.duplicate
                ? ` · ${doc.chunk_count} chunks`
                : ""}
              {doc.status === "failed" && doc.error_message ? ` · ${doc.error_message}` : ""}
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}
