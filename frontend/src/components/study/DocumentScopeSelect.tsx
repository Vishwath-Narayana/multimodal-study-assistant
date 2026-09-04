import { useDocuments } from "../../hooks/useDocuments";

interface DocumentScopeSelectProps {
  value: string | null;
  onChange: (documentId: string | null) => void;
}

export function DocumentScopeSelect({ value, onChange }: DocumentScopeSelectProps) {
  const { documents, loading } = useDocuments();

  return (
    <div className="flex flex-col gap-1">
      <label htmlFor="document-scope" className="text-xs font-medium text-text-muted">
        Scope
      </label>
      <select
        id="document-scope"
        value={value ?? ""}
        onChange={(e) => onChange(e.target.value || null)}
        disabled={loading}
        className="rounded-lg border border-border bg-surface px-3 py-2 text-sm text-text focus:outline-none focus-visible:outline focus-visible:outline-2 focus-visible:outline-accent"
      >
        <option value="">All documents</option>
        {documents.map((doc) => (
          <option key={doc.id} value={doc.id}>
            {doc.filename}
          </option>
        ))}
      </select>
    </div>
  );
}
