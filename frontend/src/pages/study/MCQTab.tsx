import { useState } from "react";
import { ApiError, studyMCQ, type MCQResponse } from "../../lib/api";
import { GenerationControls, type GenerationParams } from "../../components/study/GenerationControls";
import { AnswerableGuard } from "../../components/study/StudyResultShell";
import { EvidenceConsideredPanel } from "../../components/evidence/EvidencePanel";
import { MCQRunner } from "../../components/study/MCQRunner";
import { ErrorState, LoadingState } from "../../components/common/States";

export function MCQTab() {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<MCQResponse | null>(null);
  const [lastParams, setLastParams] = useState<GenerationParams | null>(null);

  async function generate(params: GenerationParams) {
    setLastParams(params);
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      setResult(
        await studyMCQ({
          query: params.query,
          count: params.count,
          difficulty: params.difficulty,
          document_id: params.documentId,
        })
      );
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Something went wrong. Try again.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h2 className="text-lg font-medium text-text">MCQ</h2>
        <p className="text-sm text-text-muted">
          Multiple-choice practice questions grounded in your documents.
        </p>
      </div>

      <GenerationControls
        queryPlaceholder='e.g. "CPU pipelining"'
        loading={loading}
        onSubmit={generate}
      />

      {loading && <LoadingState label="Generating questions…" />}
      {error && <ErrorState message={error} onRetry={() => lastParams && void generate(lastParams)} />}
      {result && (
        <AnswerableGuard answerable={result.answerable} reason={result.reason}>
          <MCQRunner items={result.items} />
          <div className="mt-4">
            <EvidenceConsideredPanel evidence={result.evidence} />
          </div>
        </AnswerableGuard>
      )}
    </div>
  );
}
