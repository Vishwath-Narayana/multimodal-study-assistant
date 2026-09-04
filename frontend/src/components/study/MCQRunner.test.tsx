import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, test } from "vitest";
import type { MCQItem } from "../../lib/api";
import { MCQRunner } from "./MCQRunner";

const items: MCQItem[] = [
  {
    question: "What is 2 + 2?",
    options: [
      { id: "A", text: "3" },
      { id: "B", text: "4" },
      { id: "C", text: "5" },
      { id: "D", text: "6" },
    ],
    correct_option: "B",
    explanation: "Basic arithmetic.",
    difficulty: "easy",
    citations: [
      {
        chunk_id: "c1",
        valid: true,
        status: "valid",
        document_id: "doc-1",
        filename: "math.pdf",
        page: 1,
        section: null,
      },
    ],
    source_chunk_ids: ["c1"],
  },
];

test("selecting the correct option shows feedback and updates the score", async () => {
  const user = userEvent.setup();
  render(<MCQRunner items={items} />);

  const options = screen.getAllByRole("radio");
  await user.click(options[1]); // "B" / "4"

  expect(screen.getByText("Correct.")).toBeInTheDocument();
  expect(screen.getByText("Score: 1/1")).toBeInTheDocument();
  expect(screen.getByText("Basic arithmetic.")).toBeInTheDocument();
});

test("selecting a wrong option reveals the correct answer", async () => {
  const user = userEvent.setup();
  render(<MCQRunner items={items} />);

  const options = screen.getAllByRole("radio");
  await user.click(options[0]); // "A" / "3"

  expect(screen.getByText("Incorrect — correct answer: B.")).toBeInTheDocument();
  expect(screen.getByText("Score: 0/1")).toBeInTheDocument();
});
