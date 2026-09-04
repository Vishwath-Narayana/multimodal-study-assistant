import { Link, useNavigate } from "react-router-dom";
import { useDocuments } from "../hooks/useDocuments";
import { UploadZone } from "../components/documents/UploadZone";
import { StatusBadge } from "../components/documents/StatusBadge";
import { EmptyState, ErrorState, LoadingState } from "../components/common/States";

const QUICK_ACTIONS = [
  { label: "Ask", to: "/chat" },
  { label: "Summarize", to: "/study/summary" },
  { label: "Explain", to: "/study/explain" },
  { label: "Compare", to: "/study/compare" },
  { label: "Quiz", to: "/study/quiz" },
  { label: "MCQ", to: "/study/mcq" },
  { label: "Flashcards", to: "/study/flashcards" },
] as const;

export function DashboardPage() {
  const { documents, loading, error, refresh } = useDocuments();
  const navigate = useNavigate();
  const recent = documents.slice(0, 5);

  return (
    <div className="flex flex-col gap-10">
      <div>
        <h1 className="text-2xl font-semibold text-text">Welcome back</h1>
        <p className="mt-1 text-sm text-text-muted">
          Your grounded, citation-backed study workspace.
        </p>
      </div>

      <div className="grid gap-4 sm:grid-cols-3">
        <div className="rounded-xl border border-border bg-surface px-5 py-4">
          <p className="text-xs uppercase tracking-wide text-text-muted">Documents</p>
          <p className="mt-1 text-2xl font-semibold text-text">
            {loading ? "—" : documents.length}
          </p>
        </div>
        <div className="rounded-xl border border-border bg-surface px-5 py-4 sm:col-span-2">
          <p className="text-xs uppercase tracking-wide text-text-muted">Quick actions</p>
          <div className="mt-2 flex flex-wrap gap-2">
            {QUICK_ACTIONS.map((action) => (
              <button
                key={action.label}
                type="button"
                onClick={() => navigate(action.to)}
                className="rounded-lg border border-border px-3 py-1.5 text-sm text-text transition-colors hover:border-accent focus-visible:outline focus-visible:outline-2 focus-visible:outline-accent"
              >
                {action.label}
              </button>
            ))}
          </div>
        </div>
      </div>

      <div className="flex flex-col gap-4">
        <h2 className="text-lg font-medium text-text">Upload study material</h2>
        <UploadZone onUploaded={() => void refresh()} />
      </div>

      <div className="flex flex-col gap-4">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-medium text-text">Recent documents</h2>
          {documents.length > 0 && (
            <Link to="/library" className="text-xs text-text-muted hover:text-text">
              View all →
            </Link>
          )}
        </div>
        {loading && <LoadingState label="Loading your documents…" />}
        {error && <ErrorState message={error} onRetry={refresh} />}
        {!loading && !error && recent.length === 0 && (
          <EmptyState
            title="Upload your first study document."
            description="PDF, DOCX, PPTX, HTML, or audio recordings — once uploaded, ask questions or generate study material."
          />
        )}
        {!loading && !error && recent.length > 0 && (
          <ul className="flex flex-col gap-2">
            {recent.map((doc) => (
              <li key={doc.id}>
                <Link
                  to={`/library/${encodeURIComponent(doc.id)}`}
                  className="flex items-center justify-between rounded-lg border border-border bg-surface px-4 py-2.5 text-sm text-text transition-colors hover:border-accent focus-visible:outline focus-visible:outline-2 focus-visible:outline-accent"
                >
                  <span className="truncate">{doc.filename}</span>
                  <StatusBadge status={doc.status} />
                </Link>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
