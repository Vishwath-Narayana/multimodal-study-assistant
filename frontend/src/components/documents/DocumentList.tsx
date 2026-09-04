import { useState } from "react";
import { Link } from "react-router-dom";
import type { DocumentResponse } from "../../lib/api";
import { StatusBadge } from "./StatusBadge";

function formatDate(iso: string): string {
  try {
    return new Date(iso).toLocaleString(undefined, {
      dateStyle: "medium",
      timeStyle: "short",
    });
  } catch {
    return iso;
  }
}

interface DocumentListProps {
  documents: DocumentResponse[];
  onDelete: (documentId: string) => Promise<void>;
}

export function DocumentList({ documents, onDelete }: DocumentListProps) {
  const [pendingDeleteId, setPendingDeleteId] = useState<string | null>(null);
  const [deletingId, setDeletingId] = useState<string | null>(null);

  async function confirmDelete(documentId: string) {
    setDeletingId(documentId);
    try {
      await onDelete(documentId);
    } finally {
      setDeletingId(null);
      setPendingDeleteId(null);
    }
  }

  return (
    <ul className="flex flex-col gap-3">
      {documents.map((doc) => (
        <li
          key={doc.id}
          className="flex flex-col gap-3 rounded-xl border border-border bg-surface px-5 py-4 sm:flex-row sm:items-center sm:justify-between"
        >
          <div className="flex min-w-0 flex-col gap-1">
            <Link
              to={`/library/${encodeURIComponent(doc.id)}`}
              className="truncate text-sm font-medium text-text hover:text-accent focus-visible:outline focus-visible:outline-2 focus-visible:outline-accent"
            >
              {doc.filename}
            </Link>
            <p className="text-xs text-text-muted">
              {doc.file_type.toUpperCase()} · uploaded {formatDate(doc.uploaded_at)}
              {doc.chunk_count != null ? ` · ${doc.chunk_count} chunks` : ""}
              {doc.page_count != null ? ` · ${doc.page_count} pages` : ""}
            </p>
            {doc.status === "failed" && doc.error_message && (
              <p className="text-xs text-red-400">{doc.error_message}</p>
            )}
          </div>
          <div className="flex shrink-0 items-center gap-3">
            <StatusBadge status={doc.status} />
            {pendingDeleteId === doc.id ? (
              <div className="flex items-center gap-2">
                <span className="text-xs text-text-muted">Delete?</span>
                <button
                  type="button"
                  onClick={() => void confirmDelete(doc.id)}
                  disabled={deletingId === doc.id}
                  className="rounded-lg border border-red-800/60 px-2.5 py-1 text-xs font-medium text-red-200 hover:bg-red-900/30 focus-visible:outline focus-visible:outline-2 focus-visible:outline-red-400"
                >
                  {deletingId === doc.id ? "Deleting…" : "Confirm"}
                </button>
                <button
                  type="button"
                  onClick={() => setPendingDeleteId(null)}
                  className="rounded-lg border border-border px-2.5 py-1 text-xs text-text-muted hover:text-text focus-visible:outline focus-visible:outline-2 focus-visible:outline-accent"
                >
                  Cancel
                </button>
              </div>
            ) : (
              <button
                type="button"
                onClick={() => setPendingDeleteId(doc.id)}
                aria-label={`Delete ${doc.filename}`}
                className="rounded-lg border border-border px-2.5 py-1 text-xs text-text-muted transition-colors hover:border-red-800/60 hover:text-red-300 focus-visible:outline focus-visible:outline-2 focus-visible:outline-accent"
              >
                Delete
              </button>
            )}
          </div>
        </li>
      ))}
    </ul>
  );
}
