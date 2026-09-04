import { useState } from "react";
import type { Flashcard } from "../../lib/api";
import { CitationPanel } from "../evidence/EvidencePanel";

export function FlashcardDeck({ items }: { items: Flashcard[] }) {
  const [index, setIndex] = useState(0);
  const [flipped, setFlipped] = useState(false);

  if (items.length === 0) return null;
  const card = items[index];
  const isLast = index === items.length - 1;

  function next() {
    setFlipped(false);
    setIndex((i) => Math.min(i + 1, items.length - 1));
  }

  function prev() {
    setFlipped(false);
    setIndex((i) => Math.max(i - 1, 0));
  }

  function restart() {
    setFlipped(false);
    setIndex(0);
  }

  return (
    <div className="flex flex-col items-center gap-4">
      <p className="text-xs text-text-muted">
        Card {index + 1} of {items.length} · {card.difficulty}
      </p>

      <button
        type="button"
        onClick={() => setFlipped((f) => !f)}
        aria-pressed={flipped}
        className="flex min-h-48 w-full max-w-xl flex-col items-center justify-center gap-2 rounded-2xl border border-border bg-surface px-8 py-10 text-center transition-colors hover:border-accent focus-visible:outline focus-visible:outline-2 focus-visible:outline-accent"
      >
        <span className="text-xs uppercase tracking-wide text-text-muted">
          {flipped ? "Back" : "Front"}
        </span>
        <p className="text-base text-text">{flipped ? card.back : card.front}</p>
        {flipped && card.explanation && (
          <p className="mt-2 text-sm text-text-muted">{card.explanation}</p>
        )}
        <span className="mt-3 text-xs text-text-muted">Click to flip</span>
      </button>

      {flipped && (
        <div className="w-full max-w-xl">
          <CitationPanel citations={card.citations} />
        </div>
      )}

      <div className="flex items-center gap-3">
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
          onClick={restart}
          className="rounded-lg border border-border px-3 py-1.5 text-sm text-text focus-visible:outline focus-visible:outline-2 focus-visible:outline-accent"
        >
          Restart
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
