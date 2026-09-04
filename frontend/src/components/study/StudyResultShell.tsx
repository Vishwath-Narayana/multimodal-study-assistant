import type { ReactNode } from "react";
import type { Contradictions } from "../../lib/api";
import { InsufficientEvidenceState } from "../common/States";

export function ContradictionNotice({ contradictions }: { contradictions: Contradictions }) {
  if (!contradictions.has_conflict) return null;
  return (
    <div className="rounded-lg border border-amber-900/50 bg-amber-950/20 px-4 py-2 text-xs text-amber-200">
      Sources disagree on this topic ({contradictions.conflicts.length} conflict
      {contradictions.conflicts.length === 1 ? "" : "s"} found) — check citations before relying on
      this.
    </div>
  );
}

export function AnswerableGuard({
  answerable,
  reason,
  children,
}: {
  answerable: boolean;
  reason: string | null;
  children: ReactNode;
}) {
  if (!answerable) return <InsufficientEvidenceState reason={reason} />;
  return <>{children}</>;
}
