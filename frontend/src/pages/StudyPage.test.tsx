import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Navigate, Route, Routes } from "react-router-dom";
import { afterEach, expect, test, vi } from "vitest";
import { installMockFetch, route } from "../test/mockFetch";
import { StudyPage } from "./StudyPage";
import { SummaryTab } from "./study/SummaryTab";
import { CompareTab } from "./study/CompareTab";

afterEach(() => {
  vi.unstubAllGlobals();
});

function renderStudyRoutes() {
  return render(
    <MemoryRouter initialEntries={["/study/summary"]}>
      <Routes>
        <Route path="/study" element={<StudyPage />}>
          <Route index element={<Navigate to="summary" replace />} />
          <Route path="summary" element={<SummaryTab />} />
          <Route path="compare" element={<CompareTab />} />
        </Route>
      </Routes>
    </MemoryRouter>
  );
}

test("switching study modes navigates between tabs", async () => {
  installMockFetch([route("GET", "/documents", { documents: [] })]);
  const user = userEvent.setup();
  renderStudyRoutes();

  expect(screen.getByRole("heading", { name: "Summary" })).toBeInTheDocument();

  await user.click(screen.getByRole("link", { name: "Compare" }));

  expect(await screen.findByRole("heading", { name: "Compare" })).toBeInTheDocument();
});
