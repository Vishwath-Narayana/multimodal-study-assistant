import { useDocuments } from "../hooks/useDocuments";
import { UploadZone } from "../components/documents/UploadZone";
import { DocumentList } from "../components/documents/DocumentList";
import { EmptyState, ErrorState, LoadingState } from "../components/common/States";

export function LibraryPage() {
  const { documents, loading, error, refresh, remove } = useDocuments();

  return (
    <div className="flex flex-col gap-8">
      <div>
        <h1 className="text-2xl font-semibold text-text">Document library</h1>
        <p className="mt-1 text-sm text-text-muted">
          Upload study material — PDF, DOCX, PPTX, HTML, or audio recordings.
        </p>
      </div>

      <UploadZone onUploaded={() => void refresh()} />

      {loading && <LoadingState label="Loading your documents…" />}
      {error && <ErrorState message={error} onRetry={refresh} />}
      {!loading && !error && documents.length === 0 && (
        <EmptyState
          title="No documents yet"
          description="Upload your first study document to start asking questions and generating study material."
        />
      )}
      {!loading && !error && documents.length > 0 && (
        <DocumentList documents={documents} onDelete={remove} />
      )}
    </div>
  );
}
