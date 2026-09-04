import type { ReactNode } from "react";

export function LoadingState({ label }: { label: string }) {
  return (
    <div role="status" className="flex items-center gap-3 rounded-xl border border-border bg-surface px-6 py-8 text-sm text-text-muted">
      <span
        aria-hidden="true"
        className="h-4 w-4 animate-spin rounded-full border-2 border-border border-t-accent"
      />
      <span>{label}</span>
    </div>
  );
}

export function ErrorState({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div
      role="alert"
      className="flex flex-col gap-3 rounded-xl border border-red-900/50 bg-red-950/20 px-6 py-6 text-sm text-red-200"
    >
      <p>{message}</p>
      {onRetry && (
        <button
          type="button"
          onClick={onRetry}
          className="w-fit rounded-lg border border-red-800/60 px-3 py-1.5 text-xs font-medium text-red-100 transition-colors hover:bg-red-900/30 focus-visible:outline focus-visible:outline-2 focus-visible:outline-red-400"
        >
          Try again
        </button>
      )}
    </div>
  );
}

export function EmptyState({
  title,
  description,
  action,
}: {
  title: string;
  description?: string;
  action?: ReactNode;
}) {
  return (
    <div className="flex flex-col items-center gap-2 rounded-xl border border-dashed border-border bg-surface/50 px-6 py-14 text-center">
      <p className="text-sm font-medium text-text">{title}</p>
      {description && <p className="max-w-sm text-sm text-text-muted">{description}</p>}
      {action && <div className="mt-3">{action}</div>}
    </div>
  );
}

export function InsufficientEvidenceState({ reason }: { reason?: string | null }) {
  return (
    <div className="rounded-xl border border-amber-900/50 bg-amber-950/20 px-6 py-5 text-sm text-amber-200">
      <p className="font-medium">Insufficient evidence</p>
      <p className="mt-1 text-amber-200/80">
        {reason ??
          "I couldn't find enough evidence in your selected sources to answer this confidently."}
      </p>
    </div>
  );
}
