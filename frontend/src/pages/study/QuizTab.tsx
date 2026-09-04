import { useState } from "react";
import { ApiError, studyQuiz, type QuizResponse } from "../../lib/api";
import { GenerationControls, type GenerationParams } from "../../components/study/GenerationControls";
import { AnswerableGuard } from "../../components/study/StudyResultShell";
import { EvidenceConsideredPanel } from "../../components/evidence/EvidencePanel";
import { QuizRunner } from "../../components/study/QuizRunner";
import { ErrorState, LoadingState } from "../../components/common/States";

export function QuizTab() {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<QuizResponse | null>(null);
  const [lastParams, setLastParams] = useState<GenerationParams | null>(null);

  async function generate(params: GenerationParams) {
    setLastParams(params);
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      setResult(
        await studyQuiz({
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
        <h2 className="text-lg font-medium text-text">Quiz</h2>
        <p className="text-sm text-text-muted">
          Free-response practice questions grounded in your documents.
        </p>
      </div>

      <GenerationControls
        queryPlaceholder='e.g. "cellular respiration"'
        loading={loading}
        onSubmit={generate}
      />

      {loading && <LoadingState label="Generating questions…" />}
      {error && <ErrorState message={error} onRetry={() => lastParams && void generate(lastParams)} />}
      {result && (
        <AnswerableGuard answerable={result.answerable} reason={result.reason}>
          <QuizRunner items={result.items} />
          <div className="mt-4">
            <EvidenceConsideredPanel evidence={result.evidence} />
          </div>
        </AnswerableGuard>
      )}
    </div>
  );
}
