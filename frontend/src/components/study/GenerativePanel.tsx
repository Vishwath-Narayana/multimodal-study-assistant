import { useState } from "react";
import { useSearchParams } from "react-router-dom";
import { ApiError, type SummaryResponse } from "../../lib/api";
import { CitationPanel, EvidenceConsideredPanel } from "../evidence/EvidencePanel";
import { ErrorState, LoadingState } from "../common/States";
import { DocumentScopeSelect } from "./DocumentScopeSelect";
import { AnswerableGuard, ContradictionNotice } from "./StudyResultShell";

interface GenerativePanelProps {
  title: string;
  description: string;
  queryPlaceholder: string;
  optionLabel: string;
  options: readonly { value: string; label: string }[];
  defaultOption: string;
  submit: (args: {
    query: string;
    option: string;
    documentId: string | null;
  }) => Promise<SummaryResponse>;
}

/** Shared UI for Summary and Explain — both request/response shapes are
 * identical (query + one style knob → one grounded item), so one component
 * covers both modes (spec section 17: reuse over duplicated pages). */
export function GenerativePanel({
  title,
  description,
  queryPlaceholder,
  optionLabel,
  options,
  defaultOption,
  submit,
}: GenerativePanelProps) {
  const [searchParams] = useSearchParams();
  const [query, setQuery] = useState("");
  const [option, setOption] = useState(defaultOption);
  const [documentId, setDocumentId] = useState<string | null>(searchParams.get("document"));
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<SummaryResponse | null>(null);

  async function handleSubmit() {
    if (!query.trim() || loading) return;
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      setResult(await submit({ query, option, documentId }));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Something went wrong. Try again.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h2 className="text-lg font-medium text-text">{title}</h2>
        <p className="text-sm text-text-muted">{description}</p>
      </div>

      <form
        onSubmit={(e) => {
          e.preventDefault();
          void handleSubmit();
        }}
        className="flex flex-col gap-3 sm:flex-row sm:items-end"
      >
        <div className="flex flex-1 flex-col gap-1">
          <label htmlFor="query" className="text-xs font-medium text-text-muted">
            {queryPlaceholder}
          </label>
          <input
            id="query"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder={queryPlaceholder}
            className="rounded-lg border border-border bg-surface px-3 py-2 text-sm text-text placeholder:text-text-muted focus:outline-none focus-visible:outline focus-visible:outline-2 focus-visible:outline-accent"
          />
        </div>
        <div className="flex flex-col gap-1">
          <label htmlFor="option" className="text-xs font-medium text-text-muted">
            {optionLabel}
          </label>
          <select
            id="option"
            value={option}
            onChange={(e) => setOption(e.target.value)}
            className="rounded-lg border border-border bg-surface px-3 py-2 text-sm text-text focus:outline-none focus-visible:outline focus-visible:outline-2 focus-visible:outline-accent"
          >
            {options.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>
        </div>
        <DocumentScopeSelect value={documentId} onChange={setDocumentId} />
        <button
          type="submit"
          disabled={loading || !query.trim()}
          className="rounded-lg bg-accent px-4 py-2 text-sm font-medium text-white transition-opacity hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-40 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent"
        >
          Generate
        </button>
      </form>

      {loading && <LoadingState label="Analyzing your documents…" />}
      {error && <ErrorState message={error} onRetry={handleSubmit} />}
      {result && (
        <AnswerableGuard answerable={result.answerable} reason={result.reason}>
          <div className="flex flex-col gap-4">
            <div className="rounded-xl border border-border bg-surface px-5 py-4 text-sm text-text whitespace-pre-wrap">
              {result.item?.content}
            </div>
            <ContradictionNotice contradictions={result.contradictions} />
            {result.item && <CitationPanel citations={result.item.citations} />}
            <EvidenceConsideredPanel evidence={result.evidence} />
          </div>
        </AnswerableGuard>
      )}
    </div>
  );
}
