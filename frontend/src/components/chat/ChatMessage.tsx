import type { ChatQueryResponse } from "../../lib/api";
import { CitationPanel, EvidenceConsideredPanel } from "../evidence/EvidencePanel";
import { InsufficientEvidenceState } from "../common/States";

export function UserMessage({ text }: { text: string }) {
  return (
    <div className="flex justify-end">
      <div className="max-w-2xl rounded-2xl rounded-tr-sm bg-accent/15 px-4 py-2.5 text-sm text-text">
        {text}
      </div>
    </div>
  );
}

export function AssistantMessage({ response }: { response: ChatQueryResponse }) {
  return (
    <div className="flex flex-col gap-3">
      <div className="max-w-2xl rounded-2xl rounded-tl-sm border border-border bg-surface px-4 py-3 text-sm text-text">
        {response.answerable ? (
          <p className="whitespace-pre-wrap">{response.answer}</p>
        ) : (
          <InsufficientEvidenceState reason={response.sufficiency.reason} />
        )}
      </div>
      {response.answerable && (
        <div className="max-w-2xl flex flex-col gap-3">
          {response.contradictions.has_conflict && (
            <div className="rounded-lg border border-amber-900/50 bg-amber-950/20 px-4 py-2 text-xs text-amber-200">
              Sources disagree on this topic — check the citations below before relying on this
              answer.
            </div>
          )}
          <CitationPanel citations={response.citations} />
        </div>
      )}
      <div className="max-w-2xl">
        <EvidenceConsideredPanel evidence={response.evidence} />
      </div>
    </div>
  );
}
