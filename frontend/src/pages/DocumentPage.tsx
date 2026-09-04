import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { ApiError, getDocument, type DocumentResponse } from "../lib/api";
import { StatusBadge } from "../components/documents/StatusBadge";
import { ErrorState, LoadingState } from "../components/common/States";

const STUDY_ACTIONS = [
  { mode: "summary", label: "Summarize" },
  { mode: "explain", label: "Explain" },
  { mode: "quiz", label: "Quiz" },
  { mode: "mcq", label: "MCQ" },
  { mode: "flashcards", label: "Flashcards" },
] as const;

export function DocumentPage() {
  const { documentId } = useParams<{ documentId: string }>();
  const navigate = useNavigate();
  const [document, setDocument] = useState<DocumentResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!documentId) return;
    setLoading(true);
    setError(null);
    getDocument(documentId)
      .then(setDocument)
      .catch((err) => setError(err instanceof ApiError ? err.message : "Failed to load document."))
      .finally(() => setLoading(false));
  }, [documentId]);

  if (loading) return <LoadingState label="Loading document…" />;
  if (error || !document) return <ErrorState message={error ?? "Document not found."} />;

  return (
    <div className="flex flex-col gap-8">
      <div>
        <Link to="/library" className="text-xs text-text-muted hover:text-text">
          ← Back to library
        </Link>
        <div className="mt-2 flex flex-wrap items-center gap-3">
          <h1 className="text-2xl font-semibold text-text">{document.filename}</h1>
          <StatusBadge status={document.status} />
        </div>
        <dl className="mt-3 grid grid-cols-2 gap-x-8 gap-y-1 text-sm text-text-muted sm:grid-cols-4">
          <div>
            <dt className="text-xs uppercase tracking-wide">Type</dt>
            <dd className="text-text">{document.file_type.toUpperCase()}</dd>
          </div>
          {document.page_count != null && (
            <div>
              <dt className="text-xs uppercase tracking-wide">Pages</dt>
              <dd className="text-text">{document.page_count}</dd>
            </div>
          )}
          {document.chunk_count != null && (
            <div>
              <dt className="text-xs uppercase tracking-wide">Chunks</dt>
              <dd className="text-text">{document.chunk_count}</dd>
            </div>
          )}
          <div>
            <dt className="text-xs uppercase tracking-wide">Uploaded</dt>
            <dd className="text-text">{new Date(document.uploaded_at).toLocaleDateString()}</dd>
          </div>
        </dl>
      </div>

      {document.status === "failed" && document.error_message && (
        <ErrorState message={document.error_message} />
      )}

      <div className="flex flex-col gap-3">
        <h2 className="text-sm font-medium text-text">Quick actions</h2>
        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            onClick={() =>
              navigate("/chat", { state: { prefill: `About "${document.filename}": ` } })
            }
            className="rounded-lg border border-border bg-surface px-3 py-1.5 text-sm text-text transition-colors hover:border-accent focus-visible:outline focus-visible:outline-2 focus-visible:outline-accent"
          >
            Ask about this document
          </button>
          {STUDY_ACTIONS.map((action) => (
            <button
              key={action.mode}
              type="button"
              onClick={() =>
                navigate(`/study/${action.mode}?document=${encodeURIComponent(document.id)}`)
              }
              className="rounded-lg border border-border bg-surface px-3 py-1.5 text-sm text-text transition-colors hover:border-accent focus-visible:outline focus-visible:outline-2 focus-visible:outline-accent"
            >
              {action.label}
            </button>
          ))}
        </div>
        <p className="text-xs text-text-muted">
          Chat searches across every document; study modes above are scoped to this one.
        </p>
      </div>
    </div>
  );
}
