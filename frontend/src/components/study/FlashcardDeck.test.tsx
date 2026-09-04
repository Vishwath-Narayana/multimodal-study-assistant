import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, test } from "vitest";
import type { Flashcard } from "../../lib/api";
import { FlashcardDeck } from "./FlashcardDeck";

const items: Flashcard[] = [
  {
    front: "What is the powerhouse of the cell?",
    back: "The mitochondrion.",
    explanation: "Produces ATP via cellular respiration.",
    difficulty: "easy",
    citations: [],
    source_chunk_ids: ["c1"],
  },
  {
    front: "What pigment absorbs light in photosynthesis?",
    back: "Chlorophyll.",
    explanation: null,
    difficulty: "easy",
    citations: [],
    source_chunk_ids: ["c2"],
  },
];

test("flipping a flashcard reveals the back", async () => {
  const user = userEvent.setup();
  render(<FlashcardDeck items={items} />);

  expect(screen.getByText("What is the powerhouse of the cell?")).toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: /Front/ }));

  expect(screen.getByText("The mitochondrion.")).toBeInTheDocument();
});

test("next/previous navigate between cards", async () => {
  const user = userEvent.setup();
  render(<FlashcardDeck items={items} />);

  await user.click(screen.getByRole("button", { name: "Next" }));
  expect(screen.getByText("What pigment absorbs light in photosynthesis?")).toBeInTheDocument();

  await user.click(screen.getByRole("button", { name: "Previous" }));
  expect(screen.getByText("What is the powerhouse of the cell?")).toBeInTheDocument();
});
