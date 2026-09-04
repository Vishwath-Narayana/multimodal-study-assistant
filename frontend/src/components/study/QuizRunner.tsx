import { useState } from "react";
import type { QuizQuestion } from "../../lib/api";
import { CitationPanel } from "../evidence/EvidencePanel";

export function QuizRunner({ items }: { items: QuizQuestion[] }) {
  const [index, setIndex] = useState(0);
  const [revealed, setRevealed] = useState(false);

  if (items.length === 0) return null;
  const question = items[index];
  const isLast = index === items.length - 1;

  function next() {
    setRevealed(false);
    setIndex((i) => Math.min(i + 1, items.length - 1));
  }

  function prev() {
    setRevealed(false);
    setIndex((i) => Math.max(i - 1, 0));
  }

  return (
    <div className="flex flex-col gap-4">
      <p className="text-xs text-text-muted">
        Question {index + 1} of {items.length}
      </p>
      <div className="rounded-xl border border-border bg-surface px-5 py-5">
        <p className="text-sm font-medium text-text">{question.question}</p>
        <p className="mt-1 text-xs text-text-muted capitalize">
          {question.question_type.replace("_", " ")} · {question.difficulty}
        </p>

        {revealed ? (
          <div className="mt-4 flex flex-col gap-2 border-t border-border pt-4">
            <p className="text-sm text-text">
              <span className="font-medium">Answer: </span>
              {question.expected_answer}
            </p>
            <p className="text-sm text-text-muted">{question.explanation}</p>
          </div>
        ) : (
          <button
            type="button"
            onClick={() => setRevealed(true)}
            className="mt-4 rounded-lg border border-border px-3 py-1.5 text-xs font-medium text-text hover:border-accent focus-visible:outline focus-visible:outline-2 focus-visible:outline-accent"
          >
            Reveal answer
          </button>
        )}
      </div>

      {revealed && <CitationPanel citations={question.citations} />}

      <div className="flex items-center justify-between">
        <button
          type="button"
          onClick={prev}
          disabled={index === 0}
          className="rounded-lg border border-border px-3 py-1.5 text-sm text-text disabled:cursor-not-allowed disabled:opacity-40 focus-visible:outline focus-visible:outline-2 focus-visible:outline-accent"
        >
          Previous
        </button>
        <button
          type="button"
          onClick={next}
          disabled={isLast}
          className="rounded-lg border border-border px-3 py-1.5 text-sm text-text disabled:cursor-not-allowed disabled:opacity-40 focus-visible:outline focus-visible:outline-2 focus-visible:outline-accent"
        >
          Next
        </button>
      </div>
    </div>
  );
}
