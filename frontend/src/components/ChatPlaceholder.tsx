export function ChatPlaceholder() {
  return (
    <div className="flex flex-col gap-3 rounded-xl border border-border bg-surface px-6 py-6">
      <p className="text-sm text-text-muted">
        Ask a question about your uploaded material — grounded answers with
        citations will appear here once retrieval and generation are wired up.
      </p>
      <div className="rounded-lg border border-border bg-bg px-4 py-3 text-sm text-text-muted">
        Chat input placeholder
      </div>
    </div>
  );
}
