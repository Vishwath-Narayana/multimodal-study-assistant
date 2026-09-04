import { useState } from "react";
import { useSearchParams } from "react-router-dom";
import { ApiError, studyCompare, type CompareResponse } from "../../lib/api";
import { DocumentScopeSelect } from "../../components/study/DocumentScopeSelect";
import { AnswerableGuard, ContradictionNotice } from "../../components/study/StudyResultShell";
import { CitationPanel, EvidenceConsideredPanel } from "../../components/evidence/EvidencePanel";
import { ErrorState, LoadingState } from "../../components/common/States";

export function CompareTab() {
  const [searchParams] = useSearchParams();
  const [topicA, setTopicA] = useState("");
  const [topicB, setTopicB] = useState("");
  const [documentId, setDocumentId] = useState<string | null>(searchParams.get("document"));
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<CompareResponse | null>(null);

  async function handleSubmit() {
    if (!topicA.trim() || !topicB.trim() || loading) return;
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      setResult(await studyCompare({ topic_a: topicA, topic_b: topicB, document_id: documentId }));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Something went wrong. Try again.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h2 className="text-lg font-medium text-text">Compare</h2>
        <p className="text-sm text-text-muted">Compare two topics from your study material.</p>
      </div>

      <form
        onSubmit={(e) => {
          e.preventDefault();
          void handleSubmit();
        }}
        className="flex flex-col gap-3"
      >
        <div className="grid gap-3 sm:grid-cols-2">
          <div className="flex flex-col gap-1">
            <label htmlFor="topic-a" className="text-xs font-medium text-text-muted">
              Topic A
            </label>
            <input
              id="topic-a"
              value={topicA}
              onChange={(e) => setTopicA(e.target.value)}
              placeholder="e.g. mitosis"
              className="rounded-lg border border-border bg-surface px-3 py-2 text-sm text-text placeholder:text-text-muted focus:outline-none focus-visible:outline focus-visible:outline-2 focus-visible:outline-accent"
            />
          </div>
          <div className="flex flex-col gap-1">
            <label htmlFor="topic-b" className="text-xs font-medium text-text-muted">
              Topic B
            </label>
            <input
              id="topic-b"
              value={topicB}
              onChange={(e) => setTopicB(e.target.value)}
              placeholder="e.g. meiosis"
              className="rounded-lg border border-border bg-surface px-3 py-2 text-sm text-text placeholder:text-text-muted focus:outline-none focus-visible:outline focus-visible:outline-2 focus-visible:outline-accent"
            />
          </div>
        </div>
        <div className="flex items-end gap-3">
          <DocumentScopeSelect value={documentId} onChange={setDocumentId} />
          <button
            type="submit"
            disabled={loading || !topicA.trim() || !topicB.trim()}
            className="rounded-lg bg-accent px-4 py-2 text-sm font-medium text-white transition-opacity hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-40 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent"
          >
            Compare
          </button>
        </div>
      </form>

      {loading && <LoadingState label="Analyzing your documents…" />}
      {error && <ErrorState message={error} onRetry={handleSubmit} />}
      {result && (
        <AnswerableGuard answerable={result.answerable} reason={result.reason}>
          {result.item && (
            <div className="flex flex-col gap-4">
              <ContradictionNotice contradictions={result.contradictions} />
              {result.item.incomplete_for.length > 0 && (
                <p className="text-xs text-amber-300">
                  Insufficient evidence for: {result.item.incomplete_for.join(", ")}
                </p>
              )}
              <div className="overflow-x-auto rounded-xl border border-border">
                <table className="min-w-full border-collapse text-sm">
                  <thead>
                    <tr className="bg-surface text-left text-xs uppercase tracking-wide text-text-muted">
                      <th className="border-b border-border px-4 py-2">Aspect</th>
                      <th className="border-b border-border px-4 py-2">{result.item.topic_a}</th>
                      <th className="border-b border-border px-4 py-2">{result.item.topic_b}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {result.item.aspects.map((aspect, idx) => (
                      <tr key={idx} className="border-b border-border last:border-b-0">
                        <td className="px-4 py-3 align-top font-medium text-text">
                          {aspect.aspect}
                        </td>
                        <td className="px-4 py-3 align-top text-text-muted">
                          {aspect.topic_a ?? "—"}
                        </td>
                        <td className="px-4 py-3 align-top text-text-muted">
                          {aspect.topic_b ?? "—"}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <CitationPanel
                citations={result.item.aspects.flatMap((aspect) => aspect.citations)}
              />
            </div>
          )}
          <EvidenceConsideredPanel evidence={result.evidence} />
        </AnswerableGuard>
      )}
    </div>
  );
}
