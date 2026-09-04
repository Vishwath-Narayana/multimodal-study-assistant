import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, expect, test, vi } from "vitest";
import { installMockFetch, route } from "../test/mockFetch";
import { LibraryPage } from "./LibraryPage";

afterEach(() => {
  vi.unstubAllGlobals();
});

test("empty state renders when there are no documents", async () => {
  installMockFetch([route("GET", "/documents", { documents: [] })]);

  render(
    <MemoryRouter>
      <LibraryPage />
    </MemoryRouter>
  );

  expect(await screen.findByText("No documents yet")).toBeInTheDocument();
});

test("document list renders uploaded documents", async () => {
  installMockFetch([
    route("GET", "/documents", {
      documents: [
        {
          id: "doc-1",
          filename: "notes.pdf",
          file_type: "pdf",
          file_hash: "abc",
          status: "completed",
          uploaded_at: new Date().toISOString(),
          updated_at: new Date().toISOString(),
          page_count: 3,
          title: null,
          author: null,
          subject: null,
          block_count: 10,
          chunk_count: 12,
          error_message: null,
        },
      ],
    }),
  ]);

  render(
    <MemoryRouter>
      <LibraryPage />
    </MemoryRouter>
  );

  expect(await screen.findByText("notes.pdf")).toBeInTheDocument();
});

test("API error is handled with a retryable error state", async () => {
  installMockFetch([
    route("GET", "/documents", () => ({ status: 500, body: { detail: "boom" } })),
  ]);

  render(
    <MemoryRouter>
      <LibraryPage />
    </MemoryRouter>
  );

  expect(await screen.findByRole("alert")).toHaveTextContent("boom");
  expect(screen.getByRole("button", { name: "Try again" })).toBeInTheDocument();
});

test("upload flow ingests a file and refreshes the list", async () => {
  const user = userEvent.setup();
  let uploaded = false;
  installMockFetch([
    route("GET", "/documents", () => ({
      status: 200,
      body: {
        documents: uploaded
          ? [
              {
                id: "doc-2",
                filename: "lecture.pdf",
                file_type: "pdf",
                file_hash: "xyz",
                status: "completed",
                uploaded_at: new Date().toISOString(),
                updated_at: new Date().toISOString(),
                page_count: 1,
                title: null,
                author: null,
                subject: null,
                block_count: 2,
                chunk_count: 2,
                error_message: null,
              },
            ]
          : [],
      },
    })),
    route("POST", "/documents/upload", () => {
      uploaded = true;
      return {
        status: 200,
        body: {
          document_id: "doc-2",
          filename: "lecture.pdf",
          status: "completed",
          page_count: 1,
          block_count: 2,
          chunk_count: 2,
          duplicate: false,
          error_message: null,
        },
      };
    }),
  ]);

  render(
    <MemoryRouter>
      <LibraryPage />
    </MemoryRouter>
  );

  await screen.findByText("No documents yet");

  const file = new File(["hello"], "lecture.pdf", { type: "application/pdf" });
  const input = document.querySelector('input[type="file"]') as HTMLInputElement;
  await user.upload(input, file);

  await waitFor(() => expect(screen.getByText("lecture.pdf")).toBeInTheDocument());
});
