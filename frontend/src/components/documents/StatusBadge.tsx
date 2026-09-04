const STYLES: Record<string, string> = {
  completed: "bg-emerald-950/40 text-emerald-300 border-emerald-900/50",
  duplicate: "bg-surface text-text-muted border-border",
  failed: "bg-red-950/40 text-red-300 border-red-900/50",
};

export function StatusBadge({ status }: { status: string }) {
  const style = STYLES[status] ?? "bg-surface text-text-muted border-border";
  return (
    <span className={`rounded-full border px-2.5 py-0.5 text-xs font-medium capitalize ${style}`}>
      {status}
    </span>
  );
}
