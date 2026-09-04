import { useState } from "react";
import { ApiError, studyFlashcards, type FlashcardsResponse } from "../../lib/api";
import { GenerationControls, type GenerationParams } from "../../components/study/GenerationControls";
import { AnswerableGuard } from "../../components/study/StudyResultShell";
import { EvidenceConsideredPanel } from "../../components/evidence/EvidencePanel";
import { FlashcardDeck } from "../../components/study/FlashcardDeck";
import { ErrorState, LoadingState } from "../../components/common/States";

export function FlashcardsTab() {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<FlashcardsResponse | null>(null);
  const [lastParams, setLastParams] = useState<GenerationParams | null>(null);

  async function generate(params: GenerationParams) {
    setLastParams(params);
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      setResult(
        await studyFlashcards({
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
        <h2 className="text-lg font-medium text-text">Flashcards</h2>
        <p className="text-sm text-text-muted">Flip through grounded flashcards to review.</p>
      </div>

      <GenerationControls
        queryPlaceholder='e.g. "the French Revolution"'
        loading={loading}
        onSubmit={generate}
      />

      {loading && <LoadingState label="Generating flashcards…" />}
      {error && <ErrorState message={error} onRetry={() => lastParams && void generate(lastParams)} />}
      {result && (
        <AnswerableGuard answerable={result.answerable} reason={result.reason}>
          <FlashcardDeck items={result.items} />
          <div className="mt-4">
            <EvidenceConsideredPanel evidence={result.evidence} />
          </div>
        </AnswerableGuard>
      )}
    </div>
  );
}
