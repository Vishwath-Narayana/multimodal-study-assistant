import { useState } from "react";
import type { MCQItem } from "../../lib/api";
import { CitationPanel } from "../evidence/EvidencePanel";

export function MCQRunner({ items }: { items: MCQItem[] }) {
  const [index, setIndex] = useState(0);
  const [selected, setSelected] = useState<string | null>(null);
  const [score, setScore] = useState({ correct: 0, answered: 0 });

  if (items.length === 0) return null;
  const item = items[index];
  const isLast = index === items.length - 1;
  const isAnswered = selected !== null;

  function choose(optionId: string) {
    if (isAnswered) return;
    setSelected(optionId);
    setScore((s) => ({
      correct: s.correct + (optionId === item.correct_option ? 1 : 0),
      answered: s.answered + 1,
    }));
  }

  function next() {
    setSelected(null);
    setIndex((i) => Math.min(i + 1, items.length - 1));
  }

  function prev() {
    setSelected(null);
    setIndex((i) => Math.max(i - 1, 0));
  }

  const isComplete = score.answered === items.length;

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between text-xs text-text-muted">
        <span>
          Question {index + 1} of {items.length}
        </span>
        <span>
          Score: {score.correct}/{score.answered}
        </span>
      </div>

      <fieldset className="rounded-xl border border-border bg-surface px-5 py-5">
        <legend className="px-1 text-sm font-medium text-text">{item.question}</legend>
        <div role="radiogroup" aria-label={item.question} className="mt-3 flex flex-col gap-2">
          {item.options.map((option) => {
            const isCorrect = option.id === item.correct_option;
            const isSelected = option.id === selected;
            let stateClass = "border-border hover:border-accent";
            if (isAnswered && isCorrect) stateClass = "border-emerald-700 bg-emerald-950/30";
            else if (isAnswered && isSelected) stateClass = "border-red-800 bg-red-950/30";

            return (
              <button
                key={option.id}
                type="button"
                role="radio"
                aria-checked={isSelected}
                onClick={() => choose(option.id)}
                disabled={isAnswered}
                className={`flex items-center gap-3 rounded-lg border px-4 py-2.5 text-left text-sm text-text transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-accent disabled:cursor-default ${stateClass}`}
              >
                <span className="font-medium text-text-muted">{option.id}</span>
                <span>{option.text}</span>
              </button>
            );
          })}
        </div>

        {isAnswered && (
          <div className="mt-4 flex flex-col gap-2 border-t border-border pt-4">
            <p className="text-sm text-text">
              {selected === item.correct_option ? "Correct." : `Incorrect — correct answer: ${item.correct_option}.`}
            </p>
            <p className="text-sm text-text-muted">{item.explanation}</p>
          </div>
        )}
      </fieldset>

      {isAnswered && <CitationPanel citations={item.citations} />}

      <div className="flex items-center justify-between">
        <button
          type="button"
          onClick={prev}
          disabled={index === 0}
          className="rounded-lg border border-border px-3 py-1.5 text-sm text-text disabled:cursor-not-allowed disabled:opacity-40 focus-visible:outline focus-visible:outline-2 focus-visible:outline-accent"
        >
          Previous
        </button>
        {isComplete && isLast ? (
          <p className="text-sm font-medium text-text">
            Final score: {score.correct}/{items.length}
          </p>
        ) : (
          <button
            type="button"
            onClick={next}
            disabled={isLast}
            className="rounded-lg border border-border px-3 py-1.5 text-sm text-text disabled:cursor-not-allowed disabled:opacity-40 focus-visible:outline focus-visible:outline-2 focus-visible:outline-accent"
          >
            Next
          </button>
        )}
      </div>
    </div>
  );
}
