import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, expect, test, vi } from "vitest";
import { installMockFetch, route } from "../test/mockFetch";
import { ChatPage } from "./ChatPage";

afterEach(() => {
  vi.unstubAllGlobals();
});

async function ask(query: string) {
  const user = userEvent.setup();
  render(
    <MemoryRouter>
      <ChatPage />
    </MemoryRouter>
  );
  await user.type(screen.getByLabelText("Ask a question"), query);
  await user.click(screen.getByRole("button", { name: "Ask" }));
}

test("chat request renders the answer with citations", async () => {
  installMockFetch([
    route("POST", "/chat/query", {
      request_id: "r1",
      query: "What is photosynthesis?",
      answer: "Photosynthesis converts light into chemical energy [chunk:c1].",
      answerable: true,
      sufficiency: { sufficient: true, reason: "ok" },
      evidence: [],
      citations: [
        {
          chunk_id: "c1",
          valid: true,
          status: "valid",
          document_id: "doc-1",
          filename: "biology.pdf",
          page: 42,
          section: "Photosynthesis",
        },
      ],
      grounding: { grounding_ratio: 0.9, grounded_token_count: 9, total_token_count: 10 },
      claim_groundings: [],
      contradictions: { has_conflict: false, conflicts: [] },
      timing: { total_ms: 10 },
    }),
  ]);

  await ask("What is photosynthesis?");

  expect(
    await screen.findByText("Photosynthesis converts light into chemical energy [chunk:c1].")
  ).toBeInTheDocument();
  expect(screen.getByText(/biology\.pdf/)).toBeInTheDocument();
  expect(screen.getByText(/Page 42/)).toBeInTheDocument();
});

test("insufficient evidence renders an explicit abstention state", async () => {
  installMockFetch([
    route("POST", "/chat/query", {
      request_id: "r2",
      query: "unrelated question",
      answer: "I don't have enough information to answer this.",
      answerable: false,
      sufficiency: { sufficient: false, reason: "No relevant chunks found." },
      evidence: [],
      citations: [],
      grounding: null,
      claim_groundings: [],
      contradictions: { has_conflict: false, conflicts: [] },
      timing: { total_ms: 5 },
    }),
  ]);

  await ask("unrelated question");

  expect(await screen.findByText("Insufficient evidence")).toBeInTheDocument();
  expect(screen.getByText("No relevant chunks found.")).toBeInTheDocument();
});

test("API errors render a retryable error state instead of a blank screen", async () => {
  installMockFetch([
    route("POST", "/chat/query", () => ({ status: 503, body: { detail: "LLM unavailable" } })),
  ]);

  await ask("What is photosynthesis?");

  expect(await screen.findByText("LLM unavailable")).toBeInTheDocument();
  await waitFor(() =>
    expect(screen.getByRole("button", { name: "Try again" })).toBeInTheDocument()
  );
});
