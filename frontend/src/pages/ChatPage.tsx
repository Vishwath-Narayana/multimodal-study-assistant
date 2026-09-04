import { useRef, useState } from "react";
import { useLocation } from "react-router-dom";
import { ApiError, queryChat, type ChatQueryResponse } from "../lib/api";
import { AssistantMessage, UserMessage } from "../components/chat/ChatMessage";
import { ErrorState, LoadingState } from "../components/common/States";

type Turn =
  | { role: "user"; text: string; id: string }
  | { role: "assistant"; response: ChatQueryResponse; id: string }
  | { role: "error"; message: string; retryQuery: string; id: string };

export function ChatPage() {
  const location = useLocation();
  const initialQuery = (location.state as { prefill?: string } | null)?.prefill ?? "";
  const [input, setInput] = useState(initialQuery);
  const [turns, setTurns] = useState<Turn[]>([]);
  const [loading, setLoading] = useState(false);
  const idRef = useRef(0);

  async function send(query: string) {
    if (!query.trim() || loading) return;
    const userId = `t${idRef.current++}`;
    setTurns((prev) => [...prev, { role: "user", text: query, id: userId }]);
    setInput("");
    setLoading(true);
    try {
      const response = await queryChat({ query });
      setTurns((prev) => [
        ...prev,
        { role: "assistant", response, id: `t${idRef.current++}` },
      ]);
    } catch (err) {
      setTurns((prev) => [
        ...prev,
        {
          role: "error",
          message: err instanceof ApiError ? err.message : "Something went wrong. Try again.",
          retryQuery: query,
          id: `t${idRef.current++}`,
        },
      ]);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-semibold text-text">Ask your documents</h1>
        <p className="mt-1 text-sm text-text-muted">
          Grounded answers with citations, searched across every uploaded document.
        </p>
      </div>

      <div className="flex flex-col gap-4">
        {turns.length === 0 && !loading && (
          <div className="rounded-xl border border-dashed border-border bg-surface/50 px-6 py-10 text-center text-sm text-text-muted">
            Ask a question about your uploaded material to get started.
          </div>
        )}
        {turns.map((turn) => {
          if (turn.role === "user") return <UserMessage key={turn.id} text={turn.text} />;
          if (turn.role === "assistant")
            return <AssistantMessage key={turn.id} response={turn.response} />;
          return (
            <div key={turn.id} className="max-w-2xl">
              <ErrorState message={turn.message} onRetry={() => void send(turn.retryQuery)} />
            </div>
          );
        })}
        {loading && <LoadingState label="Analyzing your documents…" />}
      </div>

      <form
        onSubmit={(e) => {
          e.preventDefault();
          void send(input);
        }}
        className="flex gap-2"
      >
        <label htmlFor="chat-input" className="sr-only">
          Ask a question
        </label>
        <input
          id="chat-input"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Ask a question about your documents…"
          disabled={loading}
          className="flex-1 rounded-xl border border-border bg-surface px-4 py-3 text-sm text-text placeholder:text-text-muted focus:outline-none focus-visible:outline focus-visible:outline-2 focus-visible:outline-accent"
        />
        <button
          type="submit"
          disabled={loading || !input.trim()}
          className="rounded-xl bg-accent px-5 py-3 text-sm font-medium text-white transition-opacity hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-40 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent"
        >
          Ask
        </button>
      </form>
    </div>
  );
}
