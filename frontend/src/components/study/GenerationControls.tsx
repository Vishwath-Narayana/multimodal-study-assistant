import type { ReactNode } from "react";
import { useState } from "react";
import { useSearchParams } from "react-router-dom";
import { DocumentScopeSelect } from "./DocumentScopeSelect";

export interface GenerationParams {
  query: string;
  count: number;
  difficulty: "easy" | "medium" | "hard";
  documentId: string | null;
}

interface GenerationControlsProps {
  queryPlaceholder: string;
  loading: boolean;
  onSubmit: (params: GenerationParams) => void;
  extra?: ReactNode;
}

export function GenerationControls({
  queryPlaceholder,
  loading,
  onSubmit,
  extra,
}: GenerationControlsProps) {
  const [searchParams] = useSearchParams();
  const [query, setQuery] = useState("");
  const [count, setCount] = useState(5);
  const [difficulty, setDifficulty] = useState<"easy" | "medium" | "hard">("medium");
  const [documentId, setDocumentId] = useState<string | null>(searchParams.get("document"));

  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        if (!query.trim() || loading) return;
        onSubmit({ query, count, difficulty, documentId });
      }}
      className="flex flex-col gap-3"
    >
      <div className="flex flex-col gap-1">
        <label htmlFor="gen-query" className="text-xs font-medium text-text-muted">
          Topic
        </label>
        <input
          id="gen-query"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder={queryPlaceholder}
          className="rounded-lg border border-border bg-surface px-3 py-2 text-sm text-text placeholder:text-text-muted focus:outline-none focus-visible:outline focus-visible:outline-2 focus-visible:outline-accent"
        />
      </div>
      <div className="flex flex-wrap items-end gap-3">
        <div className="flex flex-col gap-1">
          <label htmlFor="gen-count" className="text-xs font-medium text-text-muted">
            Count
          </label>
          <input
            id="gen-count"
            type="number"
            min={1}
            max={20}
            value={count}
            onChange={(e) => setCount(Number(e.target.value))}
            className="w-20 rounded-lg border border-border bg-surface px-3 py-2 text-sm text-text focus:outline-none focus-visible:outline focus-visible:outline-2 focus-visible:outline-accent"
          />
        </div>
        <div className="flex flex-col gap-1">
          <label htmlFor="gen-difficulty" className="text-xs font-medium text-text-muted">
            Difficulty
          </label>
          <select
            id="gen-difficulty"
            value={difficulty}
            onChange={(e) => setDifficulty(e.target.value as "easy" | "medium" | "hard")}
            className="rounded-lg border border-border bg-surface px-3 py-2 text-sm text-text focus:outline-none focus-visible:outline focus-visible:outline-2 focus-visible:outline-accent"
          >
            <option value="easy">Easy</option>
            <option value="medium">Medium</option>
            <option value="hard">Hard</option>
          </select>
        </div>
        {extra}
        <DocumentScopeSelect value={documentId} onChange={setDocumentId} />
        <button
          type="submit"
          disabled={loading || !query.trim()}
          className="rounded-lg bg-accent px-4 py-2 text-sm font-medium text-white transition-opacity hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-40 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent"
        >
          Generate
        </button>
      </div>
    </form>
  );
}
